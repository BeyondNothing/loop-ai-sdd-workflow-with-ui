# 单元测试规约（ace 基准）

> 适用节点：`design_test_cases` `review_plan_and_tests` `verify_tests`
> 来源：skill://unit-test-rule（详见 `ai-reles/unit-test-rule.md`）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选
> 注意：`split_tasks` / `implement_code` **不注入**本规约（该两节点只写生产代码，不写测试）。

## 分层归属【强制】
| 层 | 测试类型 | 示例 |
|---|---|---|
| domain | 纯单元（直接 `new`，不起 Spring） | `WithdrawalTest`、`WithdrawalRuleEvaluatorTest` |
| application | 单元/路由/契约测试（mock 仓储端口） | `WithdrawalRpcServiceTest` |
| infrastructure | Mapper 契约 + DB 集成（`@SpringBootTest`） | `WithdrawalMapperContractTest`、`*DatabaseIntegrationTest` |
| api | 契约/校验测试 | `WithdrawalContractValidationTest` |

## 框架与断言【强制】
- JUnit 5（`org.junit.jupiter.api.Test`）+ **AssertJ**（`assertThat` / `assertThatThrownBy`），统一断言风格。
- `BigDecimal` 用 `isEqualByComparingTo`（勿用 `isEqualTo`，小数精度不稳）。
- 异常断言：`assertThatThrownBy(...).isInstanceOf(XxxException.class).hasMessageContaining("...")`。

## 用例要点【强制】
- 命名行为式：`createsPendingWaitingWithdrawal`、`rejectedWithdrawalCannotBeApproved`、`duplicateSuccessfulResultIsIdempotent`；包与主代码同构。
- 领域聚合根覆盖：创建校验、状态机转换、非法转换抛异常、**幂等**（重复结果不改变已定终态）。
- 纯逻辑直接 `new`；集成才用 `@SpringBootTest` + DB(Testcontainers)。
- 断言**可观察行为/状态/异常**，不照抄实现细节。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| 单测拉起整个 Spring 上下文 | 纯逻辑 new；集成才 @SpringBootTest |
| `assertEquals` 断言 BigDecimal | AssertJ `isEqualByComparingTo` |
| mock 被测对象自身 | 测真实对象，mock 边界依赖 |
| 一测一把大杂烩 | 一个测试一个行为点 |

## 自查
- [ ] 被测对象真实、外部依赖已 mock？纯逻辑避免 Spring？
- [ ] BigDecimal 用 `isEqualByComparingTo`？断言看行为而非实现？
- [ ] 聚合状态机非法转换 + 幂等已覆盖？
