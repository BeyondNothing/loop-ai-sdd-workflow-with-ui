# 身份与安全规约（ace 基准）

> 适用节点：`analyze_requirements` `implement_code`
> 来源：skill://identity-and-authorization + sensitive-data-and-secrets（详见 `ace-development-manual` 对应分块）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 身份来源【强制】
| 场景 | Header | 解析 |
|---|---|---|
| 商家端 APP/小程序 | `login-user` | `CUserUtil.getCurrentUser()` → `CLoginUserContext` |
| 商户接口（funds） | `X-Mch-Id` | `CurrentUserContext.requireMchId()` |
| 运营写接口（funds） | `X-Operator-Id` | `CurrentUserContext.requireOperatorId()` |

- **身份一律从 Header/Context 解析，请求正文禁止携带 mchId/operatorId**。
- 取不到身份抛 `BusinessException`/`UnauthorizedException`，不默认游客。

## 鉴权边界【推荐】
- Gateway 完成 JWT 鉴权后透传 `login-user`；业务层**信任** Header，不重复验签。
- **未接网关/未补鉴权 filter 的接口禁止对外暴露**（如 merchant-boss-backend 运营接口当前零鉴权，接网关前不得开放）。
- 资金/用户数据/运营配置接口必须核对身份来源与权限。

## 敏感数据与密钥【强制】
- 敏感字段（银行卡）**明文快照仅存储、接口只返掩码**；提供统一脱敏工具（`SensitiveDataMasker`）。
- 日志禁止打印敏感字段原值（卡号/身份证/手机号/密钥）。
- **密钥/第三方凭证只走 Nacos + 环境变量，仓库不落密码**：`NACOS_SERVER_ADDR/USERNAME/PASSWORD/NAMESPACE/SERVER_PORT`；数据库/ES/Redis/MQ 由 Nacos `*-infra.yaml` 管理；COS/OMS 密钥只从 Nacos 下发。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| 请求正文传 mchId/operatorId | Header/Context 解析 |
| 业务层自行验 token | 网关鉴权 + 透传 Header |
| 零鉴权接口直接上线 | 先接网关/加 filter |
| 密钥硬编码/仓库提交密码 | Nacos + 环境变量 |
| 接口/日志返回明文卡号 | 掩码 + 日志脱敏 |

## 自查
- [ ] 身份来自 Header/Context？正文未带身份？
- [ ] 涉及资金/敏感数据接口已鉴权？零鉴权接口标注并暂缓暴露？
- [ ] 密钥只走 Nacos + 环境变量？敏感字段已掩码？
