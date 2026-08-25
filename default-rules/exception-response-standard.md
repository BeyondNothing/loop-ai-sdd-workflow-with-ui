# Spring 异常与响应用规约（ace 基准）

> 适用节点：`implement_code`
> 来源：skill://spring-exception-response（详见 `ace-development-manual`「Spring 异常响应」分块）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 统一响应【强制】
| 工程 | Web/REST | RPC |
|---|---|---|
| funds-platform | `ApiResponse` | `RpcPlainResultSupport` |
| merchant / bff / boss | `PlainResult` | `PlainResult` |

- Controller/Provider **只做参数校验 + 结果包装**；成功 `success(data)`，失败由 `GlobalExceptionHandler` 统一转，**不手动拼错误对象**。
- 业务逻辑不在 Controller；编排到 service/facade。

## 异常体系【强制】
- 业务异常用 `BusinessException`（或领域自定义，如 `WithdrawalException`），**不用**裸 `RuntimeException` 抛业务错误。
- `GlobalExceptionHandler` 集中捕获：业务异常→业务码；`UnauthorizedException`→401；校验异常（`MethodArgumentNotValidException`/`ConstraintViolationException`）→400；兜底→500 并记录日志。

## 错误码与日志【推荐】
- 错误码语义化可查（`PARAM_INVALID`/`USER_NOT_LOGIN`/`STATE_CHANGED`），避免魔法数字。
- 对外错误信息对用户可读，**不泄堆栈/敏感信息**。
- 关键业务路径打日志（谁/做了什么/结果）；`log.error` 带上下文；**禁止打印敏感字段原值**。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| Controller 拼业务/直接返回实体 | 包装响应 + 编排 |
| 到处 try-catch 吞异常 | 交给 GlobalExceptionHandler |
| 业务错误用裸 Runtime/Exception | BusinessException / 领域异常 |
| 把堆栈/敏感信息返回用户 | 语义化错误码 + 脱敏 |

## 自查
- [ ] 响应统一 `success/code/message/data`？异常交给 Handler？
- [ ] 业务异常用 BusinessException/领域异常？错误码语义化？
- [ ] 日志不打印敏感原值？外部错误信息不泄堆栈？
