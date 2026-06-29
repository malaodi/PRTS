---
trigger_keywords:
  - "创建伙伴"
  - "创建子Agent"
  - "新建伙伴"
  - "委托专家"
  - "设为伙伴"
  - "做成伙伴"
description: "指导 Agent 如何定义和创建子 Agent（伙伴）"
version: "1.0.0"
---

# subagent-creator

## 概述
此技能指导 Agent 如何将特定能力或角色定义为一个独立的子 Agent（伙伴），供 task 工具委托使用。

## 触发时机
用户在对话中说"创建一个XX专家伙伴"、"把XX能力做成伙伴"时。

## 执行流程

### 1. 明确伙伴的角色
与用户确认：
- 伙伴擅长什么领域？
- 伙伴的目标用户是谁？
- 伙伴需要哪些工具/技能？

### 2. 生成 agent.md
```markdown
---
agent_id: "{随机UUID}"
version: "1.0.0"
author: "{创建者}"
tools: ["read", "write", "bash", "web_search"]
skills: ["skill1", "skill2"]
model: "gpt-4"
---

# {伙伴名称}

## 角色定义
你是一名{角色描述}，专门负责{核心任务}。

## 核心能力
{列出伙伴的核心能力}

## 工作方式
{描述伙伴如何接收任务、处理、返回结果}

## 输出规范
{描述返回结果的格式和规范}

## 约束
{行为边界}
```

### 3. 调用 create_asset
生成 agent.md 后调用 `create_asset` 工具：
- asset_type: "subagent"
- name: 伙伴名称
- description: 伙伴的角色说明
- content: agent.md 完整内容
- visibility: "private" (默认)
- tags: ["partner", "subagent", ...领域标签]
