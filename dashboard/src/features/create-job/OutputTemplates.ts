export type OutputTemplateKey = "episodes" | "skill" | "rag";

export type OutputTemplate = {
  title: string;
  description: string;
  bestFor: string;
  sample: string;
};

export const OUTPUT_TEMPLATES: Record<OutputTemplateKey, OutputTemplate> = {
  episodes: {
    title: "逐作品 Markdown",
    description: "为每个作品生成独立的可阅读笔记，便于逐集复习、引用和二次整理。",
    bestFor: "适合需要保留完整内容脉络的系列课程、访谈和长视频。",
    sample: "# 第 1 集：开场与概念\n\n## 内容摘要\n\n## 关键观点\n\n## 时间索引",
  },
  skill: {
    title: "蒸馏 Skill",
    description: "将整个创作者的重复方法、框架和表达习惯整理为可复用的工作流。",
    bestFor: "适合沉淀可复用的创作方法，用于后续选题、写作或研究。",
    sample: "# 创作者方法 Skill\n\n## 工作流\n\n1. 定义问题\n2. 建立判断框架\n3. 输出可执行清单",
  },
  rag: {
    title: "RAG 分块",
    description: "将内容切分为适合检索增强生成的结构化知识片段。",
    bestFor: "适合接入本地知识库、问答助手或后续检索系统。",
    sample: "{\n  \"title\": \"核心观点\",\n  \"content\": \"…\",\n  \"source\": \"第 1 集\"\n}",
  },
};
