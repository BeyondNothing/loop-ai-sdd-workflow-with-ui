# API 设计规约（ace 基准）

> 适用节点：`create_plan` `design_test_cases` `review_plan_and_tests` `split_tasks` `implement_code` `verify_tests`
> 来源：skill://api-design（详见 `ai-reles/api-design.md`）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 路径与方法【强制】
- 资源用名词复数：`/api/merchant/withdrawals`；动作用 `POST /{id}/verb`（如 `approve`）；只读派生子路径 `POST .../validate`。
- 角色路由分离：商户 `/api/merchant/**`、运营 `/api/admin/**`；BFF `/merchant/**`、Boss `/manage/**`。
- 无 GET 改数据；路径层级 ≤3 层。

## 请求【强制】
- 入参 `@Valid` + JSR-303；**正文禁止带 mchId/operatorId**，身份由 Header(`X-Mch-Id`/`X-Operator-Id`/`login-user`) → `CurrentUserContext` 解析。
- 过滤用 `@RequestParam(required=false)`；复杂查询用 DTO + `@ModelAttribute`；分页 `pageNum/pageSize`。

## 响应【强制】
- 统一体 `success/code/message/data`（funds web=ApiResponse，merchant/bff/boss=PlainResult，同构）；成功 `success(data)`，失败由 `GlobalExceptionHandler` 转 `failure(code,message)`。
- DTO ↔ domain 用 assembler 转换，不返回原始实体；敏感字段（银行卡）用掩码 `bankCardNoMasked`。

## 接口变更说明文档【强制】（改代码涉及接口变更时必须）
> 无此文档 = 未完成。文档必含：**变更概述**、**Scope**（影响端/接口/调用方/环境/兼容性风险）、**接口定义**、**Mock 数据**、**影响点&迁移**。
- **Scope**：调用方用 `codegraph callers` 核对；环境是否需要回放/双跑/迁移；破坏性 → 版本化。
- **Mock 数据**：请求 JSON（完整 body、敏感字段掩码）+ 响应 `success`/`failure` 两态；字段名/类型/可空性与实际 DTO 一致。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| GET 带复杂 JSON/改数据 | POST + body / 派生子路径 |
| 正文传 mchId/operatorId | 从 Header/Context 解析 |
| Controller 写业务/返回实体 | 编排 + assembler + 包装响应 |
| 接口变更无说明文档 | 产出含 scope + mock 的变更文档 |

## 自查
- [ ] 路径/方法/身份来源符合约定？正文未带身份？
- [ ] 响应统一 `success/code/message/data`？敏感字段已掩码？
- [ ] 接口变更是否已附「说明文档 + scope + 请求/返回 JSON mock」？
