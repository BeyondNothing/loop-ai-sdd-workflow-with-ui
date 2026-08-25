# 数据库规约（ace 基准）

> 适用节点：`create_plan` `implement_code`
> 来源：skill://mybatis-database-patterns（详见 `ace-development-manual`「MyBatis 数据库」分块）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 分层【强制】
| 层 | 归属 | 内容 |
|---|---|---|
| 端口接口 | domain/repository | `XxxRepository`（返回聚合根/Optional/分页） |
| Mapper | infrastructure/mapper | 数据访问 SQL |
| DO | infrastructure/data | 表映射对象 |
| 实现 | infrastructure/repository | DO↔聚合根转换 + 端口实现 |

- 接口签名用领域类型，**不出现** DO/Mapper 概念；实现 `@Repository` 由 Spring 注入。

## 一致性与幂等【强制】
- **乐观锁**：聚合根持 `version`，更新用 `updateWithVersion`，影响行数 `!= 1` 抛「状态已变更」。
- **幂等键**：写操作先查 `findByIdempotencyKey` 再写，防重复提交。
- **事务边界**：`@Transactional` 放应用服务（一个用例一个事务）；领域服务/仓储不声明事务。
- 涉外部系统 + DB 用 `TransactionTemplate` 精确控制；`DataIntegrityViolationException` 兜底再查。

## 迁移脚本【推荐】
- Flyway，命名 `V<日期>_<序号>__<描述>.sql`（如 `V20260818_01__create_withdrawal_tables.sql`），放 `infrastructure/src/main/resources/db/migration/`。

## 敏感字段【强制】
- 需原值复用的敏感字段（银行卡）**明文快照存储**，但**所有普通接口只返掩码**；日志禁止打印明文。

## 反模式
| 反模式 | 正确做法 |
|---|---|
| domain/application 用 DO、Mapper | 面向端口，DO 留在 infra |
| 更新整表不带 version | 乐观锁 updateWithVersion |
| 事务在领域/仓储 | 事务在应用服务 |
| 迁移脚本随手命名 | `V日期_序号__描述.sql` |

## 自查
- [ ] DO/Mapper 留在 infra？接口用聚合根/Optional？
- [ ] 更新带乐观锁 version？写操作带幂等键？事务在应用服务？
- [ ] 敏感字段明文存储但接口掩码？
