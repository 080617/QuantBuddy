import { COMMUNITY_STORAGE_KEYS, STRATEGY_MODULE_STAGE_MAP } from "@/lib/community-constants";
import { createJsonStorageCodec, readLocalStorage, writeLocalStorage } from "@/lib/storage";
import { ANNA_ZHANG, createCommunitySeedPosts } from "@/mocks/community-data";
import { dashboardService } from "@/services/dashboard-service";
import type {
  CommunityAnswer, CommunityAuthor, CommunityEngagement, CommunityPost, CommunityPostFilters, CommunityWorkspaceState,
  CompleteStrategyPost, CreateCompleteStrategyPostInput, CreateFactorPostInput, CreateQuestionPostInput,
  CreateStrategyModulePostInput, FactorPost, ForkedCompleteStrategy, QuestionPost, SavedFactor,
  SavedStrategyModule, StrategyModulePost,
} from "@/types/community";

type EngagementOverlay = Pick<CommunityEngagement, "starCount" | "bookmarkCount" | "starred" | "bookmarked"> &
  Partial<Pick<CommunityEngagement, "forkCount" | "useCount">>;
type EngagementState = Record<string, EngagementOverlay>;

export interface CommunityService {
  getPosts(filters?: CommunityPostFilters): Promise<CommunityPost[]>;
  getPostById(postId: string): Promise<CommunityPost | null>;
  getDraftsByType(type: CommunityPost["type"]): Promise<CommunityPost[]>;
  getDraftById(draftId: string): Promise<CommunityPost | null>;
  deleteDraft(draftId: string): Promise<boolean>;
  toggleStar(postId: string): Promise<CommunityPost>;
  toggleBookmark(postId: string): Promise<CommunityPost>;
  toggleFollow(authorId: string): Promise<CommunityAuthor>;
  getAnswers(postId: string): Promise<CommunityAnswer[]>;
  addAnswer(postId: string, content: string): Promise<CommunityAnswer>;
  createFactorPost(input: CreateFactorPostInput): Promise<FactorPost>;
  createStrategyModulePost(input: CreateStrategyModulePostInput): Promise<StrategyModulePost>;
  createCompleteStrategyPost(input: CreateCompleteStrategyPostInput): Promise<CompleteStrategyPost>;
  createQuestionPost(input: CreateQuestionPostInput): Promise<QuestionPost>;
  saveFactorToWorkspace(postId: string): Promise<SavedFactor>;
  saveModuleToWorkspace(postId: string): Promise<SavedStrategyModule>;
  forkStrategyToWorkspace(postId: string): Promise<ForkedCompleteStrategy>;
  removeFactorFromWorkspace(postId: string): Promise<boolean>;
  removeModuleFromWorkspace(postId: string): Promise<boolean>;
  removeForkedStrategyFromWorkspace(postId: string): Promise<boolean>;
  getWorkspaceState(): Promise<CommunityWorkspaceState>;
  getSavedFactors(): Promise<SavedFactor[]>;
  getSavedModules(): Promise<SavedStrategyModule[]>;
  getForkedStrategies(): Promise<ForkedCompleteStrategy[]>;
}

const postsCodec = createJsonStorageCodec<CommunityPost[]>();
const answersCodec = createJsonStorageCodec<CommunityAnswer[]>();
const engagementCodec = createJsonStorageCodec<EngagementState>();
const followingCodec = createJsonStorageCodec<string[]>();
const factorsCodec = createJsonStorageCodec<SavedFactor[]>();
const modulesCodec = createJsonStorageCodec<SavedStrategyModule[]>();
const forksCodec = createJsonStorageCodec<ForkedCompleteStrategy[]>();

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `${prefix}-${crypto.randomUUID()}`;
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function required(value: string, label: string) {
  const clean = value.trim();
  if (!clean) throw new Error(`${label}为必填项`);
  return clean;
}

function draftValue(value: string, label: string, status: "draft" | "published") {
  return status === "draft" ? value.trim() : required(value, label);
}

function cleanTags(tags: string[] | undefined) {
  return [...new Set((tags ?? []).map((tag) => tag.trim()).filter(Boolean))];
}

async function seedPosts() {
  const [strategy, metrics] = await Promise.all([dashboardService.getStrategySummary(), dashboardService.getBacktestMetrics()]);
  return createCommunitySeedPosts(strategy, metrics);
}

async function readPosts() {
  return readLocalStorage(COMMUNITY_STORAGE_KEYS.posts, await seedPosts(), postsCodec);
}

function readEngagement() {
  return readLocalStorage(COMMUNITY_STORAGE_KEYS.engagement, {}, engagementCodec);
}

function readFollowing() {
  return readLocalStorage(COMMUNITY_STORAGE_KEYS.following, [], followingCodec);
}

function applyLocalState(post: CommunityPost, state = readEngagement(), following = readFollowing(), answerCount?: number): CommunityPost {
  const local = state[post.id];
  return {
    ...post,
    author: { ...post.author, following: following.includes(post.author.id), followerCount: post.author.followerCount + (following.includes(post.author.id) ? 1 : 0) },
    engagement: { ...post.engagement, ...local, answerCount: answerCount ?? post.engagement.answerCount },
  };
}

async function requirePost(postId: string) {
  const post = (await localCommunityService.getPostById(postId));
  if (!post) throw new Error("Community 内容不存在");
  return post;
}

function writePosts(posts: CommunityPost[]) {
  writeLocalStorage(COMMUNITY_STORAGE_KEYS.posts, posts, postsCodec);
}

async function persistPost<T extends CommunityPost>(post: T, draftId?: string): Promise<T> {
  const posts = await readPosts();
  if (!draftId) { writePosts([...posts, post]); return post; }
  const existing = posts.find((item) => item.id === draftId && item.status === "draft");
  if (!existing) { writePosts([...posts, post]); return post; }
  const updated = { ...post, id: existing.id, createdAt: existing.createdAt } as T;
  writePosts(posts.map((item) => item.id === draftId ? updated : item));
  return updated;
}

function writeEngagementCount(post: CommunityPost, field: "forkCount" | "useCount", delta: number) {
  const state = readEngagement();
  const current = { ...post.engagement, ...state[post.id] };
  state[post.id] = {
    starCount: current.starCount,
    bookmarkCount: current.bookmarkCount,
    starred: current.starred,
    bookmarked: current.bookmarked,
    forkCount: current.forkCount,
    useCount: current.useCount,
    [field]: Math.max(0, (current[field] ?? 0) + delta),
  };
  writeLocalStorage(COMMUNITY_STORAGE_KEYS.engagement, state, engagementCodec);
}

function basePost(title: string, type: CommunityPost["type"], tags: string[] | undefined, status: "draft" | "published" = "published") {
  const timestamp = new Date().toISOString();
  return { id: createId(`post-${type}`), type, author: { ...ANNA_ZHANG }, title, tags: cleanTags(tags), createdAt: timestamp, updatedAt: timestamp, engagement: { starCount: 0, answerCount: 0, bookmarkCount: 0, forkCount: 0, useCount: 0, starred: false, bookmarked: false }, status };
}

export const localCommunityService: CommunityService = {
  async getPosts(filters = {}) {
    const engagement = readEngagement(), following = readFollowing();
    const answers = readLocalStorage(COMMUNITY_STORAGE_KEYS.answers, [], answersCodec);
    const answerCounts = answers.reduce<Record<string, number>>((counts, answer) => ({ ...counts, [answer.postId]: (counts[answer.postId] ?? 0) + 1 }), {});
    let posts = (await readPosts()).filter((post) => post.status === "published").map((post) => applyLocalState(post, engagement, following, answerCounts[post.id] ?? 0));
    if (filters.type) posts = posts.filter((post) => post.type === filters.type);
    if (filters.followingOnly) posts = posts.filter((post) => post.author.following);
    if (filters.sort === "latest") posts.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    if (filters.sort === "weekly_popular") posts.sort((a, b) => (b.engagement.starCount + b.engagement.answerCount) - (a.engagement.starCount + a.engagement.answerCount));
    if (filters.sort === "most_copied") posts.sort((a, b) => ((b.engagement.forkCount ?? 0) + (b.engagement.useCount ?? 0)) - ((a.engagement.forkCount ?? 0) + (a.engagement.useCount ?? 0)));
    return posts;
  },

  async getPostById(postId) { return (await this.getPosts()).find((post) => post.id === postId) ?? null; },

  async getDraftsByType(type) {
    return (await readPosts()).filter((post) => post.status === "draft" && post.type === type).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  },

  async getDraftById(draftId) {
    return (await readPosts()).find((post) => post.id === draftId && post.status === "draft") ?? null;
  },

  async deleteDraft(draftId) {
    const posts = await readPosts();
    const draft = posts.find((post) => post.id === draftId && post.status === "draft");
    if (!draft) return false;
    writePosts(posts.filter((post) => post.id !== draftId));
    return true;
  },

  async toggleStar(postId) {
    const post = await requirePost(postId), state = readEngagement(), current = state[postId] ?? post.engagement;
    state[postId] = { ...state[postId], starCount: Math.max(0, current.starCount + (current.starred ? -1 : 1)), bookmarkCount: current.bookmarkCount, starred: !current.starred, bookmarked: current.bookmarked, forkCount: current.forkCount, useCount: current.useCount };
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.engagement, state, engagementCodec);
    return applyLocalState(post, state);
  },

  async toggleBookmark(postId) {
    const post = await requirePost(postId), state = readEngagement(), current = state[postId] ?? post.engagement;
    state[postId] = { ...state[postId], starCount: current.starCount, bookmarkCount: Math.max(0, current.bookmarkCount + (current.bookmarked ? -1 : 1)), starred: current.starred, bookmarked: !current.bookmarked, forkCount: current.forkCount, useCount: current.useCount };
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.engagement, state, engagementCodec);
    return applyLocalState(post, state);
  },

  async toggleFollow(authorId) {
    const posts = await readPosts(), author = posts.find((post) => post.author.id === authorId)?.author;
    if (!author) throw new Error("作者不存在");
    const following = readFollowing(), active = following.includes(authorId), next = active ? following.filter((id) => id !== authorId) : [...following, authorId];
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.following, next, followingCodec);
    return { ...author, following: !active, followerCount: author.followerCount + (!active ? 1 : 0) };
  },

  async getAnswers(postId) { return readLocalStorage(COMMUNITY_STORAGE_KEYS.answers, [], answersCodec).filter((answer) => answer.postId === postId); },

  async addAnswer(postId, content) {
    await requirePost(postId);
    const cleanContent = required(content, "评论内容");
    if (cleanContent.length > 1000) throw new Error("评论不能超过 1000 个字符");
    const answer: CommunityAnswer = { id: createId("answer"), postId, author: { ...ANNA_ZHANG }, content: cleanContent, createdAt: new Date().toISOString(), starCount: 0, starred: false };
    const answers = readLocalStorage(COMMUNITY_STORAGE_KEYS.answers, [], answersCodec);
    const nextAnswers = [...answers, answer];
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.answers, nextAnswers, answersCodec);
    const posts = await readPosts();
    const answerCount = nextAnswers.filter((item) => item.postId === postId).length;
    writePosts(posts.map((item) => item.id === postId ? { ...item, engagement: { ...item.engagement, answerCount } } : item));
    return answer;
  },

  async createFactorPost(input) {
    const status = input.status ?? "published", factorName = draftValue(input.factorName, "因子名称", status);
    const post: FactorPost = { ...basePost(factorName || "未命名因子草稿", "factor", input.tags, status), type: "factor", sourceWorkspaceId: input.sourceWorkspaceId, factorName, factorType: draftValue(input.factorType, "因子类型", status), factorTypeCode: input.factorTypeCode, expression: draftValue(input.expression, "因子表达式", status), description: input.description?.trim() || undefined, verification: { verificationStatus: "not_verified" } };
    return persistPost(post, input.draftId);
  },

  async createStrategyModulePost(input) {
    if (!input.moduleType || !STRATEGY_MODULE_STAGE_MAP[input.moduleType]) throw new Error("模块类型为必填项");
    const status = input.status ?? "published", moduleName = draftValue(input.moduleName, "模块名称", status);
    const post: StrategyModulePost = { ...basePost(moduleName || "未命名策略模块草稿", "strategy_module", input.tags, status), type: "strategy_module", sourceWorkspaceId: input.sourceWorkspaceId, moduleName, moduleType: input.moduleType, applicableStage: STRATEGY_MODULE_STAGE_MAP[input.moduleType], ruleSummary: draftValue(input.ruleSummary, "规则摘要", status), ruleExpression: draftValue(input.ruleExpression, "规则表达式", status), description: input.description?.trim() || undefined };
    return persistPost(post, input.draftId);
  },

  async createCompleteStrategyPost(input) {
    if (!input.sourceWorkspaceId.trim() || input.sourceStrategyId !== input.sourceWorkspaceId) throw new Error("请选择有效的 Workspace 完整策略");
    if (input.configurationSnapshot.strategyId !== input.sourceStrategyId) throw new Error("策略配置快照与 Workspace 资产不一致");
    if (input.backtestSnapshot && input.backtestRef !== "dashboard_v1") throw new Error("回测结果缺少有效的 Workspace 回测引用");
    if (input.backtestSnapshot && (!input.backtestSnapshot.backtestId.trim() || !input.backtestSnapshot.version.trim())) throw new Error("回测引用无效");
    const status = input.status ?? "published", title = draftValue(input.communityTitle, "标题", status), intro = draftValue(input.oneLineIntroduction, "一句话介绍", status);
    const post: CompleteStrategyPost = { ...basePost(title || "未命名完整策略草稿", "complete_strategy", input.tags, input.status), type: "complete_strategy", sourceWorkspaceId: input.sourceWorkspaceId, sourceStrategyId: input.sourceStrategyId, communityTitle: title, oneLineIntroduction: intro, detailedDescription: input.detailedDescription?.trim() || undefined, configurationSnapshot: input.configurationSnapshot, backtestSnapshot: input.backtestSnapshot, backtestRef: input.backtestRef };
    return persistPost(post, input.draftId);
  },

  async createQuestionPost(input) {
    const status = input.status ?? "published", title = draftValue(input.title, "标题", status);
    const post: QuestionPost = { ...basePost(title, "question", input.tags, input.status), type: "question", content: input.content?.trim() ?? "" };
    return persistPost(post, input.draftId);
  },

  async saveFactorToWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "factor") throw new Error("该内容不是因子");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.factors, [], factorsCodec), existing = assets.find((item) => item.sourcePostId === postId); if (existing) return existing;
    const asset: SavedFactor = { id: createId("saved-factor"), sourcePostId: post.id, sourceAuthorId: post.author.id, factorName: post.factorName, factorType: post.factorType, expression: post.expression, description: post.description, tags: post.tags, status: "unused", savedAt: new Date().toISOString() };
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.factors, [...assets, asset], factorsCodec); writeEngagementCount(post, "useCount", 1); return asset;
  },

  async saveModuleToWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "strategy_module") throw new Error("该内容不是策略模块");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.modules, [], modulesCodec), existing = assets.find((item) => item.sourcePostId === postId); if (existing) return existing;
    const asset: SavedStrategyModule = { id: createId("saved-module"), sourcePostId: post.id, sourceAuthorId: post.author.id, moduleName: post.moduleName, moduleType: post.moduleType, applicableStage: post.applicableStage, ruleSummary: post.ruleSummary, ruleExpression: post.ruleExpression, description: post.description, status: "unused", savedAt: new Date().toISOString() };
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.modules, [...assets, asset], modulesCodec); writeEngagementCount(post, "useCount", 1); return asset;
  },

  async forkStrategyToWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "complete_strategy") throw new Error("该内容不是完整策略");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, [], forksCodec), existing = assets.find((item) => item.sourcePostId === postId); if (existing) return existing;
    const asset: ForkedCompleteStrategy = { id: createId("forked-strategy"), sourcePostId: post.id, sourceStrategyId: post.sourceStrategyId, sourceAuthorId: post.author.id, name: `${post.configurationSnapshot.strategyName} Fork`, configurationSnapshot: post.configurationSnapshot, sourceBacktestSnapshot: post.backtestSnapshot, status: "draft", requiresRebacktest: true, forkedAt: new Date().toISOString() };
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, [...assets, asset], forksCodec); writeEngagementCount(post, "forkCount", 1); return asset;
  },

  async removeFactorFromWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "factor") throw new Error("该内容不是因子");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.factors, [], factorsCodec), next = assets.filter((item) => item.sourcePostId !== postId);
    if (next.length === assets.length) return false;
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.factors, next, factorsCodec); writeEngagementCount(post, "useCount", -1); return true;
  },

  async removeModuleFromWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "strategy_module") throw new Error("该内容不是策略模块");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.modules, [], modulesCodec), next = assets.filter((item) => item.sourcePostId !== postId);
    if (next.length === assets.length) return false;
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.modules, next, modulesCodec); writeEngagementCount(post, "useCount", -1); return true;
  },

  async removeForkedStrategyFromWorkspace(postId) {
    const post = await requirePost(postId); if (post.type !== "complete_strategy") throw new Error("该内容不是完整策略");
    const assets = readLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, [], forksCodec), next = assets.filter((item) => item.sourcePostId !== postId);
    if (next.length === assets.length) return false;
    writeLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, next, forksCodec); writeEngagementCount(post, "forkCount", -1); return true;
  },

  async getWorkspaceState() {
    return {
      factorPostIds: readLocalStorage(COMMUNITY_STORAGE_KEYS.factors, [], factorsCodec).map((item) => item.sourcePostId),
      modulePostIds: readLocalStorage(COMMUNITY_STORAGE_KEYS.modules, [], modulesCodec).map((item) => item.sourcePostId),
      forkedStrategyPostIds: readLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, [], forksCodec).map((item) => item.sourcePostId),
    };
  },

  async getSavedFactors() {
    return readLocalStorage(COMMUNITY_STORAGE_KEYS.factors, [], factorsCodec);
  },

  async getSavedModules() {
    return readLocalStorage(COMMUNITY_STORAGE_KEYS.modules, [], modulesCodec);
  },

  async getForkedStrategies() {
    return readLocalStorage(COMMUNITY_STORAGE_KEYS.forkedStrategies, [], forksCodec);
  },
};

export const communityService: CommunityService = localCommunityService;
