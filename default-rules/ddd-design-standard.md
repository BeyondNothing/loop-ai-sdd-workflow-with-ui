# DDD 工程分层规约（ace 基准）

> 适用节点：`analyze_requirements` `create_plan` `split_tasks` `implement_code`
> 来源：skill://ddd-module-layering（详见 `ai-reles/ddd-module-layering.md`）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 四层职责（参考）
| 模块 | 职责 |
|---|---|
| api | Dubbo 接口契约 + 请求/响应 DTO（**不依赖 domain**） |
| domain | 领域模型/领域服务/**repository 端口接口** |
| application | 用例编排/事务边界/**Dubbo Provider 实现** |
| infrastructure | MyBatis(mapper/DO)、Redis、MQ、ES、外部集成、**repository 实现** |

## 硬性不变项【强制】
1. `domain` 源码**禁止** import `infrastructure` 任何类型。
2. `api` 源码**禁止** import `domain` 任何类型（契约独立）。
3. `application` 源码**禁止** import `infrastructure` 实现类（只面向 domain 端口，infra 由 Spring 注入）。
4. Repository **端口接口**在 domain、**实现**在 infrastructure；接口返回 `Optional<聚合根>`，不暴露 DO。

## 聚合根【强制】
- 构造器 `private`；提供 `create(...)`（含校验）与 `restore(...)`（恢复）。
- 状态变更只走领域方法（`approve/reject/startPayout/...`），方法内先做前置状态校验，失败抛领域异常。
- 持 `version` 乐观锁；更新带版本（`updateWithVersion`），影响行数 `!= 1` 抛「状态已变更」。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| domain import infrastructure | 面向端口，infra 注入 |
| api import domain | 独立 DTO，assembler 转换 |
| application `new` infra 实现 | 通过接口注入 |
| pom 声明依赖但源码未用 | 移除冗余依赖 |
| 聚合根暴露 setter | 私有构造 + 状态领域方法 |

## 自查
- [ ] 代码所属模块正确？依赖单向、无 `domain→infra`、`api→domain`？
- [ ] 聚合根私有构造 + 状态方法 + 乐观锁 version？
- [ ] 仓储「端口在 domain、实现在 infra、接口聚合根/Optional」？
