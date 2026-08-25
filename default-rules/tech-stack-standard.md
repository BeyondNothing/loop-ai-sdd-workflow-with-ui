# 技术栈规约（ace 基准）

> 适用节点：`analyze_requirements` `create_plan` `split_tasks` `implement_code`
> 来源：skill://tech-stack（详见 `ai-reles/tech-stack.md`）
> 定级：【强制】必须遵守 / 【推荐】建议 / 【参考】可选

## 版本矩阵【强制】
| 工程 | Spring Boot | Spring Cloud Alibaba | 端口 |
|---|---|---|---|
| merchant-bff-backend | 3.3.5 | 2023.0.3.2 | 8074 |
| merchant-boss-backend | 3.5.0 | 2021.0.6.1 | 8074 |
| merchant-platform | 3.5.0 | 2021.0.6.1 | 8072 |
| funds-platform | 3.5.0 | 2021.0.6.1 | — |

统一：Java 17、Dubbo 3.3.4、Sentinel 1.8.6、Nacos、Maven 3.9+。
> ⚠️ BFF 用较新 SCA（2023.0.3.2）、其余用较新 Boot（3.5.0）+ 较旧 SCA——**升级/对齐前先确认兼容矩阵**。

## 组件用途【强制】
| 组件 | 用途 |
|---|---|
| MySQL + MyBatis + Druid | 主库；DO/Mapper 分层；Flyway 迁移 |
| Redis | 缓存、分布式锁、分布式 ID |
| RocketMQ 5.x | 异步解耦；producer/consumer + tag + 类型化消费 + 幂等 |
| Elasticsearch | 检索（infrastructure dts/es） |
| Nacos | 注册 + 配置中心；Sentinel 规则数据源 |
| hic-udk-common | PlainResult / BusinessException / CUserUtil（登录用户） |

## 配置与环境【强制】
- 配置四层：`application.yml`（自身）/ `application-common.yml`（中间件）/ `application-{env}.yml`（环境差异）/ Nacos `*-infra.yaml`（连接参数，group=`APP_CONFIG_GROUP`）。
- 多环境由 `spring.profiles.active` 切换 → 对应 Nacos namespace；Nacos 连接全走环境变量占位符，仓库不落密码。
- `spring.application.name` / `dubbo.application.name` 一致且与工程名一致；新增服务避免撞端口。

## 项目模板【推荐】
- 领域/Provider：参考 `merchant-platform`（基础能力全）或 `funds-platform`（DDD 七模块）。
- 接入层：参考 `merchant-boss-backend`（Consumer）或 `merchant-bff-backend`（BFF）。

## 自查
- [ ] 技术选型 / 版本是否在 ACE 版本矩阵内？是否用到未引入的组件？
- [ ] 配置是否分层且密钥走环境变量/Nacos？应用名与端口是否冲突？
- [ ] 新增服务是否参考既有工程模板，符合 DDD/接入层定位？
