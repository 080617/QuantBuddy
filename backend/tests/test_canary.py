from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import inspect
from pathlib import Path
import tempfile
import unittest

from backend.execution.canary import (
    CONFIRMATION, CanaryConfig, CanaryOrchestrator, CanarySessionState,
    RealCanaryGateway, build_canary_precheck, collect_canary_snapshot,
    legalize_tick, load_canary_session, map_order_status, save_canary_session,
    select_canary_order,
)
from backend.execution.exceptions import PlanningError
from backend.execution.models import CurrentPosition
from backend.execution.order_planner import build_execution_plan
from backend.futu.models import (
    OrderBookDiagnostics,
    OrderBookTop,
    OrderRecord,
    PlaceOrderResult,
    QuoteSnapshot,
    TradableQuantity,
)

from backend.tests.execution_test_helpers import account, artifact, permissive_config, validation


FIXED = datetime(2026, 7, 31, 1, 30, tzinfo=timezone.utc)


def make_plan():
    codes=[item.code for item in artifact().signals[:5]]
    quotes={code: QuoteSnapshot(code,code,10,100,False,"2026-07-31 09:30:00",0.01) for code in codes}
    maximum={code: TradableQuantity(code,10,100000,None,100) for code in codes}
    return build_execution_plan(artifact=artifact(),artifact_validation=validation(),account=account(),
        current_positions=[],recent_orders=[],quotes=quotes,maximum_quantities=maximum,
        managed_codes=set(),config=permissive_config())


def make_snapshot(plan, *, cash=None, positions=None, orders=None, suspended=False,
                  last_price=None, lot=100, max_buy=100000, quote_time="2026-07-31 09:30:00"):
    target=select_canary_order(plan)
    quotes={item.code: QuoteSnapshot(item.code,item.code,
        last_price if item.code==target.code and last_price is not None else item.limit_reference_price,
        lot if item.code==target.code else item.lot_size,
        suspended if item.code==target.code else False,quote_time,0.01)
        for item in plan.planned_buys+plan.planned_sells}
    return __import__('backend.execution.orchestrator_models',fromlist=['ShadowSnapshot']).ShadowSnapshot(
        captured_at=FIXED.isoformat(),execution_date="2026-07-31",
        account=account(cash=plan.cash_before if cash is None else cash,
                        market_value=plan.market_value_before,total_assets=plan.total_assets_before),
        positions=list(plan.current_positions) if positions is None else positions,
        recent_orders=[] if orders is None else orders,quotes=quotes,
        maximum_quantities={item.code: TradableQuantity(item.code,item.limit_reference_price,
            max_buy if item.code==target.code else 100000,None,item.lot_size) for item in plan.planned_buys},
    )


def book(plan, *, ask=None, when="2026-07-31 09:30:00", code=None):
    order=select_canary_order(plan)
    return OrderBookTop(code or order.code, ask if ask is not None else order.limit_reference_price,1000,when)


def config(**changes):
    values=dict(market="CN",trading_environment="SIMULATE",enable_simulated_orders=True,
                enable_canary=True,poll_interval_seconds=0,poll_timeout_seconds=0)
    values.update(changes); return CanaryConfig(**values)


def record(code,status="FILLED_ALL",dealt=100,avg=10):
    return OrderRecord("order-canary-1",code,None,"BUY","NORMAL",status,100,10,dealt,avg,
                       FIXED.isoformat(),FIXED.isoformat(),None)


class Clock:
    def __init__(self): self.value=FIXED
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += timedelta(seconds=max(seconds,1))


class Gateway:
    def __init__(self, records=None, on_query=None):
        self.records=list(records or []); self.place_count=0; self.cancel_count=0; self.query_count=0
        self.on_query=on_query
    def place_once(self,candidate):
        self.place_count+=1
        return PlaceOrderResult("order-canary-1",candidate.code,"BUY",candidate.canary_qty,candidate.limit_price,"SUBMITTED")
    def get_order(self,order_id):
        self.query_count+=1
        if self.on_query: self.on_query(order_id)
        return self.records.pop(0) if len(self.records)>1 else (self.records[0] if self.records else None)
    def cancel_once(self,order_id): self.cancel_count+=1; return True


class Provider:
    def __init__(self, plan, before=None, after=None, orderbook=None):
        self.plan=plan; self.before=before or make_snapshot(plan); self.after=after or self.before
        self.orderbook=orderbook or book(plan); self.calls=0
    def __call__(self,plan,day):
        self.calls+=1
        return (self.after if self.calls>=3 else self.before), self.orderbook


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd()); self.directory=Path(self.tmp.name)
        self.plan=make_plan(); self.clock=Clock()
    def tearDown(self): self.tmp.cleanup()
    def check(self,snap=None,ob=None,cfg=None,has_id=False):
        return build_canary_precheck(self.plan,snap or make_snapshot(self.plan),ob or book(self.plan),
            expected_source_hash=self.plan.source_hash,now=FIXED,config=cfg or config(),session_has_order_id=has_id)
    def runner(self,gateway=None,provider=None,cfg=None):
        return CanaryOrchestrator(config=cfg or config(),gateway=gateway or Gateway(),
            snapshot_provider=provider or Provider(self.plan),session_dir=self.directory,
            plan_loader=lambda _plan_id: self.plan,
            clock=self.clock,sleeper=self.clock.sleep)
    def paused_unsubmitted(self,gateway=None,provider=None):
        runner=self.runner(gateway,provider); session=runner.preflight(self.plan,self.plan.source_hash)
        session.state=CanarySessionState.PAUSED; save_canary_session(session,self.directory)
        return runner,session

    def test_01_stable_smallest_estimated_value_selection(self):
        expected=min(self.plan.planned_buys,key=lambda x:(x.estimated_value,x.code,x.sequence))
        self.assertEqual(select_canary_order(self.plan).code,expected.code)
    def test_02_canary_quantity_is_one_current_lot(self): self.assertEqual(self.check().candidate.canary_qty,100)
    def test_03_non_plan_order_book_code_is_rejected(self):
        self.assertIn("ORDER_BOOK_CODE_MISMATCH",{x.code for x in self.check(ob=book(self.plan,code="SH600999")).blockers})
    def test_04_non_cn_is_rejected(self):
        snap=make_snapshot(self.plan); snap=replace(snap,account=replace(snap.account,market="US"))
        self.assertIn("NON_CN_MARKET",{x.code for x in self.check(snap=snap).blockers})
    def test_05_non_simulate_is_rejected(self):
        snap=make_snapshot(self.plan); snap=replace(snap,account=replace(snap.account,trading_environment="REAL"))
        self.assertIn("REAL_ENVIRONMENT_REJECTED",{x.code for x in self.check(snap=snap).blockers})
    def test_06_both_switches_are_required(self):
        for cfg in [config(enable_canary=False),config(enable_simulated_orders=False)]:
            with self.assertRaises(PlanningError): cfg.require_write_enabled()
    def test_07_bad_confirmation_never_places(self):
        gateway=Gateway(); session=self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:"no",output_fn=lambda _:None)
        self.assertEqual(session.state,CanarySessionState.ABORTED_BY_USER); self.assertEqual(gateway.place_count,0)
    def test_08_confirmation_forces_second_precheck(self):
        provider=Provider(self.plan); self.runner(Gateway([record(select_canary_order(self.plan).code)]),provider).execute(
            self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertGreaterEqual(provider.calls,3)
    def test_09_unfinished_order_prevents_place(self):
        code=select_canary_order(self.plan).code; pending=record(code,"SUBMITTED",0,None)
        gateway=Gateway(); provider=Provider(self.plan,before=make_snapshot(self.plan,orders=[pending]))
        session=self.runner(gateway,provider).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.place_count,0); self.assertIn("UNFINISHED_ORDER_CONFLICT",{x.code for x in session.blockers})
    def test_10_existing_order_id_never_resubmits(self):
        gateway=Gateway(); session=self.runner(gateway).preflight(self.plan,self.plan.source_hash)
        session.order_id="known"; session.place_attempted=True
        from backend.execution.canary import save_canary_session
        save_canary_session(session,self.directory)
        with self.assertRaises(PlanningError): self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION)
        self.assertEqual(gateway.place_count,0)
    def test_11_order_id_is_saved_before_query(self):
        def assertion(_):
            files=list(self.directory.glob("canary-*.canary.json")); self.assertTrue(files)
            self.assertEqual(load_canary_session(files[0].name.split(".canary")[0],self.directory).order_id,"order-canary-1")
        gateway=Gateway([record(select_canary_order(self.plan).code)],assertion)
        self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
    def test_12_missing_best_ask_blocks(self): self.assertIn("BEST_ASK_MISSING",{x.code for x in self.check(ob=book(self.plan,ask=0)).blockers})
    def test_13_stale_book_blocks(self): self.assertIn("ORDER_BOOK_STALE",{x.code for x in self.check(ob=book(self.plan,when="2026-07-31 09:00:00")).blockers})
    def test_14_price_band_blocks(self): self.assertIn("PRICE_BAND_EXCEEDED",{x.code for x in self.check(ob=book(self.plan,ask=20)).blockers})
    def test_15_maximum_quantity_blocks(self): self.assertIn("MAX_BUY_INSUFFICIENT",{x.code for x in self.check(snap=make_snapshot(self.plan,max_buy=0)).blockers})
    def test_16_cash_blocks(self): self.assertIn("INSUFFICIENT_CASH",{x.code for x in self.check(snap=make_snapshot(self.plan,cash=1)).blockers})
    def test_17_full_fill_reconciles(self):
        code=select_canary_order(self.plan).code; after=make_snapshot(self.plan,positions=[CurrentPosition(code,100,100,10,1000,True)],cash=99000)
        session=self.runner(Gateway([record(code)]),Provider(self.plan,after=after)).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(session.state,CanarySessionState.CANARY_FILLED); self.assertEqual(session.reconciliation.reconciliation_difference,0)
    def test_18_partial_fill_cancels_remainder(self):
        code=select_canary_order(self.plan).code; after=make_snapshot(self.plan,positions=[CurrentPosition(code,40,40,10,400,True)],cash=99600)
        gateway=Gateway([record(code,"FILLED_PART",40,10),record(code,"CANCELLED_PART",40,10)])
        session=self.runner(gateway,Provider(self.plan,after=after)).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.cancel_count,1); self.assertEqual(session.state,CanarySessionState.CANARY_PARTIALLY_FILLED)
    def test_19_unfilled_timeout_cancels(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"SUBMITTED",0,None),record(code,"CANCELLED_ALL",0,None)])
        runner=self.runner(gateway,cfg=config(poll_timeout_seconds=0,poll_interval_seconds=0))
        session=runner.execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.cancel_count,1); self.assertEqual(session.state,CanarySessionState.CANARY_CANCELLED_NO_FILL)
    def test_20_cancel_is_followed_by_final_query(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"FILLED_PART",40),record(code,"CANCELLED_PART",40)])
        self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertGreaterEqual(gateway.query_count,2)
    def test_21_rejected_does_not_retry(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"SUBMIT_FAILED",0,None)])
        session=self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.place_count,1); self.assertEqual(session.state,CanarySessionState.REJECTED)
    def test_22_unknown_does_not_retry_or_cancel(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"MYSTERY",0,None)])
        session=self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual((gateway.place_count,gateway.cancel_count),(1,0)); self.assertEqual(session.state,CanarySessionState.UNKNOWN_REQUIRES_REVIEW)
    def test_23_query_failure_does_not_resubmit(self):
        class Bad(Gateway):
            def get_order(self,order_id): self.query_count+=1; raise TimeoutError()
        gateway=Bad(); session=self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.place_count,1); self.assertEqual(session.state,CanarySessionState.UNKNOWN_REQUIRES_REVIEW)
    def test_24_recovery_status_only_queries(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code)])
        session=self.runner(gateway).preflight(self.plan,self.plan.source_hash); session.order_id="order-canary-1"
        from backend.execution.canary import save_canary_session
        save_canary_session(session,self.directory); self.runner(gateway).status(session.session_id)
        self.assertEqual(gateway.place_count,0); self.assertEqual(gateway.query_count,1)
    def test_25_one_session_places_at_most_once(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"MYSTERY",0,None)])
        session=self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        with self.assertRaises(PlanningError): self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION)
        self.assertEqual(gateway.place_count,1)
    def test_26_one_session_cancels_at_most_once(self):
        code=select_canary_order(self.plan).code; gateway=Gateway([record(code,"FILLED_PART",40),record(code,"CANCELLED_PART",40)])
        self.runner(gateway).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertEqual(gateway.cancel_count,1)
    def test_27_no_modify_price_api(self): self.assertNotIn("modify_order",inspect.getsource(RealCanaryGateway))
    def test_28_fill_never_completes_full_plan(self):
        code=select_canary_order(self.plan).code; after=make_snapshot(self.plan,positions=[CurrentPosition(code,100,100,10,1000,True)])
        session=self.runner(Gateway([record(code)]),Provider(self.plan,after=after)).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertFalse(session.full_plan_completed)
    def test_29_fill_requires_new_plan(self):
        code=select_canary_order(self.plan).code; after=make_snapshot(self.plan,positions=[CurrentPosition(code,100,100,10,1000,True)])
        session=self.runner(Gateway([record(code)]),Provider(self.plan,after=after)).execute(self.plan,self.plan.source_hash,input_fn=lambda _:CONFIRMATION,output_fn=lambda _:None)
        self.assertTrue(session.requires_new_plan)
    def test_30_context_managers_are_used(self):
        source=inspect.getsource(RealCanaryGateway)+inspect.getsource(collect_canary_snapshot)
        self.assertGreaterEqual(source.count("with FutuClient() as client"),4)
    def test_31_tick_legalization_rounds_up(self): self.assertEqual(legalize_tick(10.001,0.01),10.01)
    def test_32_status_mapping_is_conservative(self): self.assertEqual(map_order_status("unexpected"),"UNKNOWN")
    def test_33_reconcile_only_reads_known_order_and_account(self):
        code=select_canary_order(self.plan).code; after=make_snapshot(
            self.plan,positions=[CurrentPosition(code,100,100,10,1000,True)],cash=99000)
        gateway=Gateway([record(code)])
        session=self.runner(gateway).preflight(self.plan,self.plan.source_hash)
        session.order_id="order-canary-1"; session.place_attempted=True
        from backend.execution.canary import save_canary_session
        save_canary_session(session,self.directory)
        recovered=self.runner(gateway,Provider(self.plan,before=after,after=after)).reconcile(session.session_id)
        self.assertEqual(recovered.state,CanarySessionState.CANARY_FILLED)
        self.assertEqual((gateway.place_count,gateway.cancel_count,gateway.query_count),(0,0,1))
    def test_34_preflight_persists_safe_order_book_diagnostics(self):
        snapshot=make_snapshot(self.plan); order_book=book(self.plan)
        diagnostic=OrderBookDiagnostics(True,2,None,"2026-07-31 09:30:00",0,10,15,10)
        provider=lambda _plan,_day:(snapshot,order_book,diagnostic)
        session=self.runner(provider=provider).preflight(self.plan,self.plan.source_hash)
        payload=session.to_dict()
        self.assertEqual(payload["order_book_diagnostics"]["order_book_attempt_count"],2)
        self.assertIn("ORDER_BOOK_FRESHNESS_ACQUISITION",{event["type"] for event in payload["events"]})
    def test_35_positive_ask_without_fresh_time_is_order_book_stale(self):
        diagnostic=OrderBookDiagnostics(True,10,None,None,None,10,15,10)
        result=build_canary_precheck(
            self.plan,make_snapshot(self.plan),None,
            expected_source_hash=self.plan.source_hash,now=FIXED,config=config(),
            order_book_diagnostics=diagnostic,
        )
        codes={blocker.code for blocker in result.blockers}
        self.assertIn("ORDER_BOOK_STALE",codes)
        self.assertNotIn("BEST_ASK_MISSING",codes)
    def test_36_paused_never_submitted_session_can_preflight_again(self):
        runner,_=self.paused_unsubmitted()
        resumed=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(resumed.state,CanarySessionState.READY)
    def test_37_repeated_preflight_reuses_session_id(self):
        runner,session=self.paused_unsubmitted()
        self.assertEqual(runner.preflight(self.plan,self.plan.source_hash).session_id,session.session_id)
    def test_38_repeated_preflight_preserves_and_appends_events(self):
        runner,session=self.paused_unsubmitted(); original=list(session.events)
        resumed=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(resumed.events[:len(original)],original)
        self.assertEqual([event["type"] for event in resumed.events[-2:]],
                         ["PREFLIGHT_STARTED","PREFLIGHT_COMPLETED"])
    def test_39_repeated_preflight_never_places(self):
        gateway=Gateway(); runner,_=self.paused_unsubmitted(gateway)
        runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(gateway.place_count,0)
    def test_40_repeated_preflight_never_cancels_or_modifies(self):
        gateway=Gateway(); runner,_=self.paused_unsubmitted(gateway)
        runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(gateway.cancel_count,0)
        self.assertNotIn("modify",inspect.getsource(CanaryOrchestrator.preflight))
    def test_41_repeated_preflight_keeps_place_count_zero(self):
        runner,_=self.paused_unsubmitted(); resumed=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(resumed.place_call_count,0)
        self.assertFalse(resumed.place_attempted)
    def test_42_repeated_preflight_creates_no_second_intent_or_session(self):
        runner,session=self.paused_unsubmitted(); resumed=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(resumed.candidate.code,session.candidate.code)
        self.assertEqual(len(list(self.directory.glob("*.canary.json"))),1)
    def test_43_successful_recheck_moves_paused_session_to_ready(self):
        runner,_=self.paused_unsubmitted()
        self.assertEqual(runner.preflight(self.plan,self.plan.source_hash).state,CanarySessionState.READY)
    def test_44_failed_recheck_remains_paused(self):
        stale=book(self.plan,when="2026-07-31 09:00:00")
        provider=Provider(self.plan,orderbook=stale); runner=self.runner(provider=provider)
        first=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(first.state,CanarySessionState.PAUSED)
        second=runner.preflight(self.plan,self.plan.source_hash)
        self.assertEqual(second.state,CanarySessionState.PAUSED)
    def test_45_existing_order_id_blocks_preflight(self):
        runner,session=self.paused_unsubmitted(); session.order_id="known-order"; save_canary_session(session,self.directory)
        with self.assertRaises(PlanningError): runner.preflight(self.plan,self.plan.source_hash)
    def test_46_place_attempted_blocks_preflight(self):
        runner,session=self.paused_unsubmitted(); session.place_attempted=True; save_canary_session(session,self.directory)
        with self.assertRaises(PlanningError): runner.preflight(self.plan,self.plan.source_hash)
    def test_47_positive_place_call_count_blocks_preflight(self):
        runner,session=self.paused_unsubmitted(); session.place_call_count=1; save_canary_session(session,self.directory)
        with self.assertRaises(PlanningError): runner.preflight(self.plan,self.plan.source_hash)
    def test_48_source_hash_change_blocks_resume(self):
        runner,_=self.paused_unsubmitted(); changed=replace(self.plan,source_hash="changed")
        with self.assertRaises(PlanningError): runner.preflight(changed,changed.source_hash)
    def test_49_completed_session_cannot_preflight_again(self):
        runner,session=self.paused_unsubmitted(); session.state=CanarySessionState.CANARY_FILLED
        save_canary_session(session,self.directory)
        with self.assertRaises(PlanningError): runner.preflight(self.plan,self.plan.source_hash)
    def test_50_submission_metadata_blocks_preflight(self):
        for field_name,value in [("submitted_at",FIXED.isoformat()),("initial_status","SUBMITTED"),("final_status","CANCELLED")]:
            with self.subTest(field=field_name):
                with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
                    runner=CanaryOrchestrator(config=config(),gateway=Gateway(),snapshot_provider=Provider(self.plan),
                        session_dir=Path(directory),plan_loader=lambda _plan_id:self.plan,
                        clock=self.clock,sleeper=self.clock.sleep)
                    session=runner.preflight(self.plan,self.plan.source_hash); session.state=CanarySessionState.PAUSED
                    setattr(session,field_name,value); save_canary_session(session,Path(directory))
                    with self.assertRaises(PlanningError): runner.preflight(self.plan,self.plan.source_hash)


if __name__ == "__main__": unittest.main()
