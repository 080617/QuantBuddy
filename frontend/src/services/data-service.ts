import { apiDataService } from "@/services/api-service";
import { dashboardService, type DashboardService } from "@/services/dashboard-service";
import { mockDataService } from "@/services/mock-service";
import type { EquityPoint } from "@/types/backtest";
import type { CommunityStrategySummary } from "@/types/community";
import type { QuantModel } from "@/types/model";
import type { PaperPosition } from "@/types/paper";
import type { Strategy } from "@/types/strategy";

export interface AuxiliaryDataService {
  getModels(): Promise<readonly QuantModel[]>;
  getEquityCurve(): Promise<readonly EquityPoint[]>;
  getPaperPositions(): Promise<readonly PaperPosition[]>;
  getCommunityStrategies(): Promise<readonly CommunityStrategySummary[]>;
}

export interface DataService extends AuxiliaryDataService, DashboardService {
  getStrategies(): Promise<readonly Strategy[]>;
}

const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA !== "false";

const auxiliaryDataService = useMockData ? mockDataService : apiDataService;

export const dataService: DataService = {
  ...auxiliaryDataService,
  ...dashboardService,
};
