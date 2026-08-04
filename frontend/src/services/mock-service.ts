import type { AuxiliaryDataService } from "@/services/data-service";

export const mockDataService: AuxiliaryDataService = {
  getModels: () => Promise.resolve([]),
  getEquityCurve: () => Promise.resolve([]),
  getPaperPositions: () => Promise.resolve([]),
  getCommunityStrategies: () => Promise.resolve([]),
};
