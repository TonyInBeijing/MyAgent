---
name: hello-math
description: 当用户需要计算、单位换算、验算数字或做数学运算时使用
tools:
  - calculator
  - now
---

# Hello Math

你现在启用了数学技能。

规则：

1. 凡是算术、加减乘除、幂运算，**必须**调用 `calculator`，不要心算。
2. 把完整表达式传给 `calculator`（例如 `(12 * 34) + 5`）。
3. 拿到工具结果后，用一句话向用户解释答案。
4. 若用户只是闲聊、与数学无关，不要强行调用计算器。
