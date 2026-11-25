# API 设计规范（项目占位）

> 本文件由 `ai-rules.yaml` 挂到 `design_api` / `implement_code`，注入对应 prompt 的 `{{ai_rules}}`。
> 请按你们项目的真实接口约定改写。

## 硬性要求

1. 技术方案确认后才能出 API 设计；API 设计未确认不进入代码实现。
2. 每个接口必须写全：请求（路径/查询/请求体字段表）、响应（示例 JSON + 字段表）、错误码。
3. 字段命名必须与技术方案「术语清单」的英文命名一致。
4. 示例 JSON 字段完整，前端可直接照此 mock。
5. 禁止「同上」「略」「按需添加」这类占位表述。

## 本项目约定（改成你们的真实约定）

- 路径风格：`<如：/api/v1/resource，资源用复数名词>`
- 路径前缀 / 版本：`<如：/api/v1>`
- 鉴权：`<如：Authorization: Bearer <token>；或 Session Cookie>`
- 分页：`<如：page / page_size，默认 20，需返回 total>`
- 排序：`<如：sort_by + order=asc|desc>`
- 时间格式：`<如：ISO8601 带时区，或毫秒时间戳>`
- 金额字段：`<如：统一用分（整数），字段名以 _cents 结尾>`
- 错误响应结构：`<如：{"code": "BIZ_XXX", "message": "...", "trace_id": "..."}>`
- 错误码分段：`<如：4xxxx 客户端 / 5xxxx 服务端；业务码按模块分段>`
- 幂等要求：`<如：写接口需支持 Idempotency-Key>`
