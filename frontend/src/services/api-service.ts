import type { AuxiliaryDataService } from "@/services/data-service";

function notImplemented(): never {
  throw new Error("Not implemented in Phase 1");
}

export const apiDataService: AuxiliaryDataService = {
  getModels: notImplemented,
  getEquityCurve: notImplemented,
  getPaperPositions: notImplemented,
  getCommunityStrategies: notImplemented,
};
