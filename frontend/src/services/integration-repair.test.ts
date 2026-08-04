import { beforeEach, describe, expect, it } from "vitest";
import { communityService } from "@/services/community-service";
import {
  createFactorPublishPrefill,
  createModulePublishPrefill,
  createStrategyPublishPrefill,
  resolveCompleteStrategyPreselection,
} from "@/services/workspace-integration";
import { workspaceService, WorkspaceValidationError } from "@/services/workspace-service";

class MemoryStorage implements Storage {
  private values = new Map<string, string>();
  get length() { return this.values.size; }
  clear() { this.values.clear(); }
  getItem(key: string) { return this.values.get(key) ?? null; }
  key(index: number) { return [...this.values.keys()][index] ?? null; }
  removeItem(key: string) { this.values.delete(key); }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

beforeEach(() => {
  Object.defineProperty(globalThis, "window", { configurable: true, value: { localStorage: new MemoryStorage() } });
});

describe("Backtest Context", () => {
  it("只为显式绑定 dashboard_v1 的基准策略返回 ready", async () => {
    const snapshot = await workspaceService.getSnapshot();
    const baseline = snapshot.completeStrategies.find((item) => item.backtestRef === "dashboard_v1");
    expect(baseline).toBeDefined();
    expect(await workspaceService.resolveBacktestContext(baseline?.id)).toMatchObject({ status: "ready", backtestRef: "dashboard_v1" });
  });

  it("草稿和 Community Fork 返回 not_backtested，不存在 ID 返回 not_found", async () => {
    const draft = await workspaceService.createCompleteStrategy({ name: "草稿策略", universe: "沪深300", factorAssetIds: ["builtin-mom20"], modelId: "linear", modelName: "Linear", moduleSelections: {}, status: "draft" });
    expect(await workspaceService.resolveBacktestContext(draft.id)).toMatchObject({ status: "not_backtested" });
    const fork = await communityService.forkStrategyToWorkspace("post-complete-strategy-lightgbm");
    expect(await workspaceService.resolveBacktestContext(fork.id)).toMatchObject({ status: "not_backtested" });
    expect(await workspaceService.resolveBacktestContext("missing-strategy")).toEqual({ status: "not_found", strategy: null });
  });
});

describe("创建完整策略预选", () => {
  it("合并 factorId、factorSetId，并把 moduleId 放进对应槽位", async () => {
    const snapshot = await workspaceService.getSnapshot();
    const base = { stock_selection: "builtin-stock-top5", weighting: "builtin-equal-weight", rebalance: "builtin-daily-rebalance", risk_control: "builtin-market-risk" };
    const factor = resolveCompleteStrategyPreselection(snapshot, ["qlib-alpha158"], base, { factorId: "builtin-mom20" });
    expect(factor.factorIds).toEqual(["qlib-alpha158", "builtin-mom20"]);
    const factorSet = resolveCompleteStrategyPreselection(snapshot, [], base, { factorSetId: "qlib-alpha158" });
    expect(factorSet.factorIds).toEqual(["qlib-alpha158"]);
    const moduleResult = resolveCompleteStrategyPreselection(snapshot, [], base, { moduleId: "builtin-market-risk" });
    expect(moduleResult.modules.risk_control).toBe("builtin-market-risk");
  });

  it("无效 ID 不写入配置", async () => {
    const snapshot = await workspaceService.getSnapshot();
    const result = resolveCompleteStrategyPreselection(snapshot, [], {}, { factorId: "missing", factorSetId: "missing-set", moduleId: "missing-module" });
    expect(result.factorIds).toEqual([]);
    expect(result.modules).toEqual({});
    expect(result.notices).toHaveLength(3);
  });
});

describe("Workspace 发布预填", () => {
  it("映射 factor、module 和 strategy，且无回测策略不继承基准指标", async () => {
    const snapshot = await workspaceService.getSnapshot();
    const factor = createFactorPublishPrefill(snapshot.factors[0]);
    expect(factor.sourceWorkspaceId).toBe(snapshot.factors[0].id);
    expect(factor.expression).toBe(snapshot.factors[0].expression);
    const modulePrefill = createModulePublishPrefill(snapshot.strategyModules[0]);
    expect(modulePrefill.moduleType).toBe(snapshot.strategyModules[0].moduleType);
    const draft = await workspaceService.createCompleteStrategy({ name: "无回测策略", description: "配置介绍", universe: "沪深300", factorAssetIds: ["builtin-mom20"], modelId: "linear", modelName: "Linear", moduleSelections: {}, status: "draft" });
    const prefill = createStrategyPublishPrefill(await workspaceService.getSnapshot(), draft);
    expect(prefill.sourceWorkspaceId).toBe(draft.id);
    expect(prefill.backtest).toBeUndefined();
  });
});

describe("Community 草稿", () => {
  it("支持创建、更新、重新读取、发布转换和删除", async () => {
    const created = await communityService.createFactorPost({ factorName: "草稿因子", factorType: "动量因子", factorTypeCode: "momentum", expression: "Ref($close, 1)", status: "draft" });
    const updated = await communityService.createFactorPost({ factorName: "已更新因子", factorType: "动量因子", factorTypeCode: "momentum", expression: "$close / Ref($close, 1)", status: "draft", draftId: created.id });
    expect(updated.id).toBe(created.id);
    expect((await communityService.getDraftById(created.id))?.title).toBe("已更新因子");
    expect(await communityService.getDraftsByType("factor")).toHaveLength(1);
    const published = await communityService.createFactorPost({ factorName: "已发布因子", factorType: "动量因子", factorTypeCode: "momentum", expression: "$close / Ref($close, 1)", status: "published", draftId: created.id });
    expect(published.id).toBe(created.id);
    expect(await communityService.getDraftById(created.id)).toBeNull();
    expect((await communityService.getPosts({ type: "factor" })).some((post) => post.id === created.id)).toBe(true);
    const disposable = await communityService.createQuestionPost({ title: "待删除草稿", status: "draft" });
    expect(await communityService.deleteDraft(disposable.id)).toBe(true);
    expect(await communityService.getDraftById(disposable.id)).toBeNull();
  });
});

describe("Factor Set Service 校验", () => {
  it("拒绝少于两个、去重后不足、嵌套因子集和已删除/不存在引用", async () => {
    const expectCode = async (factorIds: string[], code: string) => {
      try {
        await workspaceService.createFactorSet({ name: "非法因子集", factorIds, status: "ready" });
        throw new Error("expected validation error");
      } catch (error) {
        expect(error).toBeInstanceOf(WorkspaceValidationError);
        expect((error as WorkspaceValidationError).code).toBe(code);
      }
    };
    await expectCode(["builtin-mom20"], "FACTOR_SET_TOO_SMALL");
    await expectCode(["builtin-mom20", "builtin-mom20"], "FACTOR_SET_TOO_SMALL");
    await expectCode(["qlib-alpha158", "builtin-mom20"], "FACTOR_SET_NESTING_NOT_ALLOWED");
    await expectCode(["builtin-mom20", "deleted-factor"], "FACTOR_SET_REFERENCE_NOT_FOUND");
  });
});
