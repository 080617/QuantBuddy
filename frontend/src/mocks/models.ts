export interface QuantModel {
  id: string;
  name: string;
  tags: string[];
  description: string;
  available: true;
}

export const QUANT_MODELS: QuantModel[] = [
  { id: "lightgbm", name: "LightGBM（新手友好）", tags: ["梯度提升树", "高效训练", "表格数据"], description: "适合处理大量结构化因子，训练速度快，是经典且稳健的量化基线。", available: true },
  { id: "xgboost", name: "XGBoost", tags: ["梯度提升树", "正则化", "经典模型"], description: "逐轮拟合残差，并通过正则化控制复杂度，适合学习非线性因子关系。", available: true },
  { id: "catboost", name: "CatBoost", tags: ["梯度提升树", "有序提升", "稳健训练"], description: "利用有序提升减少过拟合，对类别型与混合特征较友好。", available: true },
  { id: "linear", name: "Linear", tags: ["线性模型", "易解释", "训练快速"], description: "以线性关系连接因子与收益，结构简单，适合作为可解释基线。", available: true },
  { id: "mlp", name: "MLP", tags: ["神经网络", "非线性", "表格特征"], description: "多层全连接网络，可学习多个因子之间的非线性组合关系。", available: true },
  { id: "dnn", name: "DNN", tags: ["深度网络", "多层表示", "高容量"], description: "使用更深的全连接结构学习复杂模式，表达能力强，但需要更多调参。", available: true },
  { id: "lstm", name: "LSTM", tags: ["循环网络", "长期依赖", "时间序列"], description: "通过门控记忆保留较长历史信息，适合学习序列中的长期依赖。", available: true },
  { id: "gru", name: "GRU", tags: ["循环网络", "轻量门控", "时间序列"], description: "以较少的门控结构完成序列记忆，参数通常少于 LSTM，训练更轻量。", available: true },
  { id: "alstm", name: "ALSTM", tags: ["注意力机制", "LSTM", "关键时点"], description: "在 LSTM 基础上加入注意力，为更重要的时间步和信息分配更高权重。", available: true },
  { id: "tcn", name: "TCN", tags: ["因果卷积", "并行训练", "长感受野"], description: "通过扩张因果卷积捕捉长序列模式，同时支持较高效的并行训练。", available: true },
  { id: "transformer", name: "Transformer", tags: ["自注意力", "全局依赖", "序列建模"], description: "通过自注意力直接连接不同时间位置，擅长学习序列中的全局关系。", available: true },
  { id: "localformer", name: "Localformer", tags: ["局部模式", "注意力", "短期结构"], description: "在 Transformer 中强化邻近时间片的局部关系，并兼顾较长范围的信息。", available: true },
  { id: "tft", name: "TFT", tags: ["时序融合", "变量选择", "可解释性"], description: "融合静态与动态变量，并通过变量选择和注意力分析多变量时间序列。", available: true },
  { id: "tabnet", name: "TabNet", tags: ["表格数据", "特征选择", "序列注意力"], description: "在多个决策阶段动态选择重要特征，兼顾非线性建模与特征解释。", available: true },
  { id: "sfm", name: "SFM", tags: ["频率建模", "周期模式", "序列记忆"], description: "在频域中维护状态记忆，用于识别金融序列中的周期和频率模式。", available: true },
  { id: "gats", name: "GATs", tags: ["图注意力", "股票关系", "动态权重"], description: "将股票视为图节点，并通过注意力学习不同股票关系的重要程度。", available: true },
  { id: "hist", name: "HIST", tags: ["行业概念", "隐藏概念", "图模型"], description: "同时利用预定义概念和隐藏概念，融合个股信息与股票间的共享信息。", available: true },
  { id: "igmtf", name: "IGMTF", tags: ["实例图", "动态关系", "多变量时序"], description: "针对不同样本动态构建变量关系图，融合跨股票和跨序列的信息。", available: true },
  { id: "master", name: "MASTER", tags: ["市场引导", "股票关联", "动态选因子"], description: "利用市场状态指导特征选择，并建模股票内部与股票之间的时序关联。", available: true },
  { id: "tra", name: "TRA", tags: ["多市场状态", "动态路由", "模式切换"], description: "使用多个预测器学习不同交易模式，再由路由器选择更合适的模式。", available: true },
  { id: "doubleensemble", name: "DoubleEnsemble", tags: ["集成学习", "样本重加权", "特征选择"], description: "同时进行样本重加权和特征选择，以降低金融数据噪声和过拟合。", available: true },
  { id: "add", name: "ADD", tags: ["信息解耦", "自蒸馏", "数据增强"], description: "分离市场收益与超额收益信息，并通过动态自蒸馏与增强减少干扰。", available: true },
  { id: "adarnn", name: "AdaRNN", tags: ["分布漂移", "自适应时序", "域适应"], description: "刻画并匹配不同时间阶段的数据分布，以适应市场状态随时间变化。", available: true },
];

if (QUANT_MODELS.length !== 23) {
  throw new Error("QuantBuddy must expose exactly 23 selectable models.");
}
