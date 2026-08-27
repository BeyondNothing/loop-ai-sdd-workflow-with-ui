---
name: code-rule
description: 编写高质量 Java 新代码的强制规范（语法约束为 Java 8，禁用 record、var 等高版本语法糖），首要原则是优先参考并遵循项目已有架构风格与实现惯例。POJO 优先使用 Lombok 注解（@Data、@Builder、@RequiredArgsConstructor、@Slf4j 等）代替手写大量 getter/setter。每条规则均附正反例。用于用户要求编写、实现、新增 Java 功能、类、接口、枚举、Service、工具方法或模块时，覆盖架构风格识别与对齐、DDD 分层设计、枚举建模、命名、常量、集合并发、异常日志、单元测试与阿里巴巴 Java 开发手册（嵩山版）核心规约。触发词：写代码、实现功能、新增接口、开发模块、写一个类/Service/方法。
agent_created: true
---

# Java 代码编写规范

编写新 Java 代码时，先对齐项目已有风格，再按领域建模，最后按规约落地实现。每条规则下方均给出 ✅ 正例 与 ❌ 反例；输出前逐条对照本规范全文（含文末阿里巴巴规约详版）。

**首要原则：优先参考项目的架构风格。** 动手写代码前，必须先识别项目实际的架构风格（DDD 四层、经典三层、六边形等）、模块划分、依赖方向、技术栈选型与包组织方式，新代码必须落在项目既有架构的相应位置并沿用其约定；项目已有架构风格与本规范默认规则冲突时，以项目风格为准，并在交付说明中注明差异。

```
✅ 项目为经典三层时，业务逻辑写在 Service，Controller 只做参数校验与结果转换
❌ 项目为经典三层，却在 Controller 里写完 SQL 调用与业务判断，另搞一套写法
```

## 执行顺序

1. 识别项目架构风格：确认分层结构（DDD / 三层 / 其他）、模块划分、依赖方向、技术栈与包组织方式。完成标准：能说明新代码应归属的层、模块和包，及该层已有的典型实现方式。
2. 阅读需求涉及的模块：同层已有实现、相邻功能的领域模型、项目依赖与包结构。完成标准：能说明现有实现的处理方式，并确定参照对象。
3. 确定风格基准：选取同层、同职责且质量最高的已有实现作为参照，沿用其命名、分层、异常处理、对象转换和注释风格；无参照时采用本规范默认风格并说明。完成标准：已明确参照对象，或已说明将采用的最简风格。
4. 领域建模：识别固定取值集合、聚合边界、领域行为与应用层编排的划分，先定枚举和领域对象，再写流程代码。完成标准：领域概念已落为类型而非魔法值。
5. 编写实现：按下方各节规约完成代码、注释与日志；单元测试随实现同步编写。
6. 验证：运行编译、静态检查和测试；无法运行时明确说明未验证项。完成标准：验证通过，或准确报告失败原因和影响。

## 新代码风格对齐（架构优先）

- 写任何新代码前，先识别并遵循项目的架构风格：新类按项目既有分层归位（如 Controller 不写业务逻辑、domain 不依赖外层），不因个人习惯另设层次或包结构。

```
✅ 项目 domain 层已按"聚合分包"组织，新建 OrderRefund 相关类放入 domain/order/refund/
❌ 在顶层建一个 util 包，把领域逻辑、转换逻辑、常量全部塞进去
```

- 写任何新代码前，先阅读同包或同模块中已有实现，沿用其命名习惯、异常处理方式、参数校验位置、返回值包装和日志写法。

```
✅ 项目统一返回 Result<T> 包装，新接口也返回 Result<OrderVO>
❌ 同项目里新接口自己 new 一个 ApiResponse<T>，与既有返回体系并存
```

- 同一概念在代码库中只有一种写法：工具调用、日期格式化、金额计算、分页封装等均复用既有实现，不另起风格。

```
✅ 项目已有 PageHelper 分页写法，新查询沿用 PageHelper.startPage(...)
❌ 新查询自己写 limit 拼接 SQL，同库出现两套分页方式
```

- 已有领域概念存在对应枚举或工具类时，必须直接复用，不得新建重复定义。

```
✅ 已存在枚举 OrderStatus，直接 import 使用 OrderStatus.PAID
❌ 又新建一个 OrderStatusEnum，成员与 OrderStatus 完全相同
```

- 项目实际架构与规范默认分层不一致时，按项目实际架构执行并在交付说明中注明。

## DDD 设计规范

项目采用 DDD 分层时，遵守以下约束：

- domain 层中具有固定取值集合的业务概念（如订单状态、用户类型、支付渠道、审核结果）必须定义为 Java 枚举类型，禁止使用 `String`、`Integer` 等原始类型加魔法值或常量类代替。

```java
❌ if ("PAID".equals(order.getStatus())) { ... }
❌ private static final int STATUS_PAID = 2;

✅ if (OrderStatus.PAID.equals(order.getStatus())) { ... }
✅ public enum OrderStatus { PENDING, PAID, CLOSED }
```

- 新建枚举时参照同模块已有枚举的结构：若已有枚举携带 `code`、`description` 属性及静态查询方法（如 `getByCode`），新枚举保持一致；枚举放在领域模型所属包内，不放到通用工具包。

```java
✅ public enum RefundStatus {
      PENDING(0, "待处理"), APPROVED(1, "已同意"), REJECTED(2, "已拒绝");
      private final int code;
      private final String description;
      public static RefundStatus getByCode(int code) { ... }
  }

❌ public enum RefundStatus { PENDING, APPROVED }   // 已有枚举都带 code/description，这个不带
❌ 把 RefundStatus 放到 common/util/enums 包里
```

- 保持依赖方向：domain 层不依赖 infrastructure、controller 等外层；枚举、领域对象的转换逻辑放在转换器或应用层，不在 domain 内引入 DTO/VO。

```java
❌ // domain/order/Order.java
  import com.xxx.interfaces.controller.dto.OrderDTO;

✅ // domain 层只有 Order 与 OrderStatus；OrderConverter（应用层/转换器）负责 Order -> OrderVO
```

- 业务规则优先收敛到领域对象或领域服务中实现，避免在应用层写过程式业务逻辑导致领域模型贫血。

```java
❌ // 应用层里写：if (order.getStatus() == 2 && amount.compareTo(limit) > 0) { order.setStatus(3); }

✅ // Order 域对象上：order.approve(operator) 内部完成状态流转与规则校验
```

- 领域对象内的集合属性不暴露可变引用，提供领域行为方法修改内部状态。

```java
❌ public List<OrderItem> getItems() { return items; }

✅ public List<OrderItem> getItems() { return Collections.unmodifiableList(items); }
✅ public void addItem(OrderItem item) { /* 校验后加入 */ }
```

## 项目工具约定

使用代码库已有依赖和调用风格，优先搜索并复用项目已有工具类；无合适方法时补充为职责最匹配的已有工具类的公共方法并补测试。默认工具选择：

| 场景 | 必须使用 |
| --- | --- |
| 字符串为空 | `org.apache.commons.lang3.StringUtils.isBlank(...)` |
| 字符串非空 | `org.apache.commons.lang3.StringUtils.isNotBlank(...)` |
| 对象为空 | `java.util.Objects.isNull(...)` |
| 对象非空 | `java.util.Objects.nonNull(...)` |
| Map 为空 | `org.apache.commons.collections4.MapUtils.isEmpty(...)` |
| Map 非空 | `org.apache.commons.collections4.MapUtils.isNotEmpty(...)` |
| 集合为空 | `org.apache.commons.collections4.CollectionUtils.isEmpty(...)` |
| 集合非空 | `org.apache.commons.collections4.CollectionUtils.isNotEmpty(...)` |
| JSON 解析与序列化 | `com.alibaba.fastjson.JSON` |

先检查目标模块是否已有对应 import 和依赖；复用现有版本，不擅自更换 JSON 库或引入同类依赖。

```java
❌ if (str == null || str.trim().isEmpty()) { ... }
❌ if (list == null || list.size() == 0) { ... }
❌ if (map == null || map.isEmpty()) { ... }

✅ if (StringUtils.isBlank(str)) { ... }
✅ if (CollectionUtils.isEmpty(list)) { ... }
✅ if (MapUtils.isEmpty(map)) { ... }
```

```java
❌ Order o = new Gson().fromJson(json, Order.class);      // 项目统一用 fastjson
✅ Order o = JSON.parseObject(json, Order.class);
```

## 语法版本约束（Java 8）

- 目标语法级别固定为 **Java 8**，仅使用 Java 8 及以下语法，不引入高版本语法糖；以项目 `pom.xml` 的 `maven.compiler.source/target` 或 build.gradle 配置为准，本项目默认按 8 执行。
- 禁止使用 `var`（Java 10）、`record`（Java 14）、文本块 `"""`（Java 13）、箭头 switch 表达式（Java 14）、`instanceof` 模式匹配（Java 14）、密封类 `sealed`（Java 15）等 Java 8 之后才有的语法。

```java
❌ var orderList = new ArrayList<Order>();
❌ record Point(int x, int y) {}
❌ String sql = """
        select * from t_order
        """;
❌ switch (status) { case PAID -> doRefund(); }
❌ if (obj instanceof Order order) { order.pay(); }

✅ List<Order> orderList = new ArrayList<>();
✅ @Getter @RequiredArgsConstructor public class Point { private final int x; private final int y; }
✅ String sql = "select * from t_order";
✅ switch (status) { case PAID: doRefund(); break; default: break; }
✅ if (obj instanceof Order) { Order order = (Order) obj; order.pay(); }
```

- 禁止使用 Java 8 之后新增的 API：`List.of` / `Map.of` / `Set.of`（Java 9）、`Optional.or` / `ifPresentOrElse` / 无参 `orElseThrow`（Java 9）、`Stream.toList()`（Java 16）、`String.isBlank` / `repeat` / `strip`（Java 11）等。

```java
❌ List<String> tags = List.of("a", "b");
❌ Map<String, Integer> map = Map.of("a", 1);
❌ List<Long> ids = orders.stream().map(Order::getId).toList();
❌ Optional.ofNullable(order).or(() -> Optional.of(defaultOrder));
❌ if (name.isBlank()) { ... }

✅ List<String> tags = Collections.unmodifiableList(Arrays.asList("a", "b"));
✅ Map<String, Integer> map = new HashMap<>(2); map.put("a", 1); ...
✅ List<Long> ids = orders.stream().map(Order::getId).collect(Collectors.toList());
✅ Optional.ofNullable(order).orElseGet(() -> defaultOrder);
✅ if (StringUtils.isBlank(name)) { ... }
```

- 不可变集合与集合初始化使用 `Collections.unmodifiableList(...)`、`Arrays.asList(...)` 或项目已有工具；Stream 收集一律写全 `collect(Collectors.toList())` / `Collectors.toMap(...)`，不使用 `.toList()`。

```java
❌ List<Order> result = orders.stream().filter(o -> o.isPaid()).toList();
❌ Set<Long> ids = orders.stream().map(Order::getId).collect(Collectors.toSet()); // 若需要去重顺序，看下条

✅ List<Order> result = orders.stream().filter(Order::isPaid).collect(Collectors.toList());
```

- 局部变量、字段、方法返回值一律显式声明类型；POJO 一律优先使用 Lombok 注解生成存取方法，禁止手写大量 getter/setter；仅当项目未引入 Lombok 时才手写，且仅编写实际被用到的存取方法。

```java
❌ var userId = request.getUserId();

✅ Long userId = request.getUserId();
✅ // 项目引入了 Lombok（默认首选）
  @Data
  @Builder
  public class CreateOrderCmd { private Long userId; private BigDecimal amount; }

✅ // 项目未引入 Lombok 时才手写，且只写用到的
  public class CreateOrderCmd {
      private Long userId;
      public Long getUserId() { return userId; }
      public void setUserId(Long userId) { this.userId = userId; }
  }
```

- 编写完成后自查一遍 import 与语法，凡编译器标记需要更高版本的写法立即改写为 Java 8 等价实现。

## Lombok 使用规范

- **优先使用 Lombok 注解代替手写 getter/setter/toString/equals/hashCode/构造器**，禁止在 POJO 中手写几十个 `getXxx()` / `setXxx()` 样板代码；注解选择沿用项目已有用法（架构优先），无参照时按下方场景表选择。

```java
❌ public class CreateOrderCmd {
      private Long userId;
      private BigDecimal amount;
      private String remark;
      private Integer channel;
      public Long getUserId() { return userId; }
      public void setUserId(Long userId) { this.userId = userId; }
      // ... 其余字段全部手写 getter/setter/toString
  }

✅ @Data
  @Builder
  public class CreateOrderCmd {
      private Long userId;
      private BigDecimal amount;
      private String remark;
      private Integer channel;
  }
```

- 按场景选择注解，不用冷门注解（`@FieldDefaults`、`@Delegate`、`@Synchronized` 等）：

| 场景 | 注解 |
| --- | --- |
| DTO / VO / Cmd / BO 等纯数据载体 | `@Data` |
| 只读值对象、不可变对象 | `@Getter` + `@RequiredArgsConstructor` + `@Value`（字段声明 `private final`） |
| 日志声明 | `@Slf4j` |
| Spring 组件构造器注入 | `@RequiredArgsConstructor` + 字段声明 `private final` |
| 字段较多或需清晰构造的构建场景 | `@Builder` |
| JPA / MyBatis 等实体类 | `@Getter` + `@Setter`，慎用 `@Data` |

```java
❌ // 构造器注入手写构造方法
  @Service
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PayClient payClient;
      public OrderService(OrderRepository orderRepository, PayClient payClient) {
          this.orderRepository = orderRepository;
          this.payClient = payClient;
      }
  }

✅ @Slf4j
  @Service
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PayClient payClient;
  }
```

```java
❌ private static final Logger log = LoggerFactory.getLogger(OrderService.class);

✅ @Slf4j   // 类上直接声明，日志用 log.info(...)
```

- 继承场景下 `@Data` 生成的 `equals/hashCode` 不含父类字段，必须显式加 `@EqualsAndHashCode(callSuper = true)`。

```java
❌ @Data
  public class RefundOrder extends BaseOrder { private BigDecimal refundAmount; }
  // equals/hashCode 丢失父类字段

✅ @Data
  @EqualsAndHashCode(callSuper = true)
  public class RefundOrder extends BaseOrder { private BigDecimal refundAmount; }
```

- 实体类（JPA/Hibernate）避免 `@Data`：`equals/hashCode` 触发延迟加载、`@Data` 的 setter 破坏不可变性设计；参照项目已有实体写法，通常用 `@Getter @Setter`。

```java
❌ @Data
  @Entity
  public class OrderDO { ... }   // equals 触发代理字段，延迟加载异常

✅ @Getter
  @Setter
  @Entity
  public class OrderDO { ... }
```

- `@Builder` 会生成全参私有构造器；类需被序列化框架（JSON 反序列化、RPC）创建时，必须补 `@NoArgsConstructor`（和 `@AllArgsConstructor`），否则反序列化报错。

```java
❌ @Builder
  public class UserDTO { ... }   // JSON 反序列化找不到无参构造器

✅ @Data
  @Builder
  @NoArgsConstructor
  @AllArgsConstructor
  public class UserDTO { ... }
```

- 不用 Lombok 的 `@Accessors(chain = true)` 等改变 setter 语义的注解，除非项目已统一使用；MyBatis 部分版本与其不兼容。
- 项目完全未引入 Lombok 时不擅自新增该依赖（架构优先），手写存取方法并只写实际用到的。

## 命名与常量（阿里巴巴规约精选）

- 类名使用 `UpperCamelCase`；方法名、变量名使用 `lowerCamelCase`；常量名全大写下划线分隔；杜绝不规范拼音与英文混拼。
- 变量命名允许使用约定俗成的缩写（如 `msg`、`info`、`config`、`num`、`cnt`、`btn`），但必须一眼能看出业务含义；禁止使用 `a`、`b`、`c`、`e`、`o`、`t`、`temp` 这类无语义单字母或无意义命名，无法从名字推断其用途即视为不合格。

```java
❌ class usermanager { }
❌ class YongHuGuanLi { }
❌ int a = orderDao.count();          // 单字母无语义
❌ int a1 = orderDao.countUnpaid();
❌ Order o = orderDao.findById(id);   // o 看不出是什么
❌ String t = cmd.getAddress();       // t 无语义

✅ class UserManager { }
✅ int unpaidOrderCnt = orderDao.countUnpaid();          // cnt 为约定俗成缩写，含义清晰
✅ Order order = orderDao.findById(id);
✅ String addr = cmd.getAddress();                        // addr 是可识别的常用缩写
```

- 循环变量与泛型参数允许使用惯例短名：`for (int i = 0; ...)`、`for (String s : list)`、`<T>`、`<K, V>`；但嵌套超过两层或循环体较长时，应改用能表达元素含义的名字。

```java
✅ for (int i = 0; i < items.size(); i++) { ... }
✅ for (Order order : orders) { ... }          // 更推荐直接写明元素含义
❌ Map<String, Map<String, List<xxx>>> 中三层 lambda 参数全部写 (a, b) -> ...
```

- 抽象类以 `Abstract` 或 `Base` 开头；异常类以 `Exception` 结尾；测试类以被测类名开头、`Test` 结尾。

```java
❌ class BaseAbstractHandler { }
❌ class PayError extends RuntimeException { }
❌ class TestOrder { }

✅ abstract class AbstractHandler { }
✅ class PayException extends RuntimeException { }
✅ class OrderServiceTest { }
```

- 枚举类名建议带语义后缀（如 `OrderStatus`），枚举成员全大写下划线分隔。

```java
❌ enum status { paid, closed }

✅ enum OrderStatus { PENDING_PAY, PAID, CLOSED }
```

- 不允许任何魔法值（未定义的常量）直接出现在代码中；立即在所属常量类或对应枚举中定义后再使用。

```java
❌ if (user.getType() == 3) { ... }
❌ if ("PENDING_REFUND".equals(task.getState())) { ... }

✅ if (user.getType() == UserType.ENTERPRISE.getCode()) { ... }
✅ if (RefundTaskState.PENDING.equals(task.getState())) { ... }
```

- 长整型 `Long` 赋值使用大写 `L`，不用小写 `l`。

```java
❌ long timeout = 10000l;
✅ long timeout = 10000L;
```

完整的阿里巴巴 Java 开发手册（嵩山版）核心规约见文末「阿里巴巴规约详版」，编码前通读，编码中按需检索。

## 方法与类设计

- 单个方法总行数不超过 80 行；方法圈复杂度控制在可读范围，超过时按职责拆分为子方法。

```java
❌ /** 单方法 200 行：查询、校验、计算、落库、发消息全部堆在一起 */

✅ public void processRefund(Long orderId) {
      validateOrder(orderId);
      RefundResult result = calculateRefund(orderId);
      saveRefund(result);
      notifyUser(result);
  }
```

- 方法参数不超过 5 个，超过时封装为参数对象。

```java
❌ public void createOrder(Long userId, Long skuId, int count, BigDecimal amount, String address, String couponId) { ... }

✅ public void createOrder(CreateOrderCmd cmd) {
      // CreateOrderCmd 封装以上字段
  }
```

- **空值与异常路径优先返回，正常逻辑不嵌套**：所有 null 检查、非法输入、空结果、越界等分支一律用卫语句写在方法最前面并提前 return（或抛异常）；正常业务路径保持在方法末尾的**顶层不嵌套**，禁止把正常逻辑包进 `if (x != null) { ... }` 的深层块或 `else` 分支里。一个方法读下来应当是「先排雷、后走路」，主流程永远零缩进到底。

```java
❌ public Result<OrderVO> detail(Long id) {
      if (id != null) {
          Order order = orderDao.findById(id);
          if (order != null) {
              if (order.isDeleted() == false) {
                  return Result.ok(convert(order));
              }
          }
      }
      return Result.fail("订单不存在");
  }

✅ public Result<OrderVO> detail(Long id) {
      if (Objects.isNull(id)) {
          return Result.fail("订单不存在");
      }
      Order order = orderDao.findById(id);
      if (Objects.isNull(order) || order.isDeleted()) {
          return Result.fail("订单不存在");
      }
      return Result.ok(convert(order));
  }
```

```java
❌ // 正常逻辑被包在 else 深层
  public void notify(Order order) {
      User buyer = userDao.findById(order.getBuyerId());
      if (Objects.nonNull(buyer)) {
          if (StringUtils.isNotBlank(buyer.getPhone())) {
              smsClient.send(buyer.getPhone(), template);
          } else {
              log.warn("Order-notify-buyer phone is blank, orderId={}", order.getId());
          }
      } else {
          log.warn("Order-notify-buyer not found, orderId={}", order.getId());
      }
  }

✅ // 空路径前置返回，正常逻辑零嵌套
  public void notify(Order order) {
      User buyer = userDao.findById(order.getBuyerId());
      if (Objects.isNull(buyer)) {
          log.warn("Order-notify-buyer not found, orderId={}", order.getId());
          return;
      }
      if (StringUtils.isBlank(buyer.getPhone())) {
          log.warn("Order-notify-buyer phone is blank, orderId={}", order.getId());
          return;
      }
      smsClient.send(buyer.getPhone(), template);
  }
```

- 对简单的映射、过滤、匹配、分组和聚合使用清晰的 Lambda 与 Stream 链；复杂控制流、异常处理或有副作用的逻辑保留普通循环；Stream 中禁止隐式异常处理逻辑。

```java
✅ List<Long> paidOrderIds = orders.stream()
      .filter(o -> OrderStatus.PAID.equals(o.getStatus()))
      .map(Order::getId)
      .collect(Collectors.toList());

❌ // 60 行嵌套 Stream 链，中间夹杂 try/catch 与外部状态修改 —— 应还原为普通循环
❌ list.stream().map(x -> { try { return parse(x); } catch (Exception e) { return null; } })  // 吞异常
```

- 优先使用不可变对象与局部变量；类成员最小可见性，能 `private` 就不 `public`。

```java
❌ public List<OrderItem> items;          // public 可变字段

✅ private List<OrderItem> items;
```

## 异常与日志

- 不要捕获 Java 类库中定义的继承自 `RuntimeException` 的运行时异常并吞掉堆栈；异常要么处理，要么转换后重新抛出，禁止捕获后什么都不做。

```java
❌ try { doPay(); } catch (Exception e) { }

✅ try {
      doPay();
  } catch (PayException e) {
      log.error("OrderService-pay-支付失败 orderId={}", orderId, e);
      throw e;
  }
```

- 不要用异常做流程控制、条件判断。

```java
❌ try { order = orderDao.findById(id); } catch (NullPointerException e) { order = new Order(); }

✅ Order order = orderDao.findById(id);
  if (Objects.isNull(order)) {
      order = new Order();
  }
```

- 事务方法中不得将异常捕获后吞掉导致事务不回滚。

```java
❌ @Transactional
  public void saveOrder(Order order) {
      try { orderDao.insert(order); } catch (Exception e) { log.error("..."); }
  }

✅ @Transactional
  public void saveOrder(Order order) {
      orderDao.insert(order);   // 异常直接抛出，事务正常回滚
  }
```

- 使用项目中的日志框架类（如 SLF4J 门面），禁止直接使用 `System.out`、`printStackTrace()`。

```java
❌ System.out.println("订单创建成功 " + orderId);
❌ e.printStackTrace();

✅ log.info("OrderService-create-订单创建成功 orderId={}", orderId);
✅ log.error("OrderService-create-订单创建失败 orderId={}", orderId, e);
```

- 日志消息固定为 `{当前类名简版}-{当前方法名}-{备注}`，三部分以半角连字符连接，中间不含空格；备注使用简洁中文，包含排障所需上下文；敏感信息不得写入日志。

```java
❌ log.info("订单：" + orderId + " 手机号：" + user.getMobile());  // 拼接且含敏感信息
❌ log.info("success");                                            // 无类名方法名，无上下文

✅ log.info("HiagentDisasterInfoSyncJob-sync-未查询到国内省市数据");
✅ log.info("OrderService-create-订单创建成功 orderId={} userId={}", orderId, userId);
```

## 单元测试

- 新增业务代码同步编写单元测试，测试类与被测类同包，命名为 `被测类Test`。

```
✅ OrderService 的测试类：src/test/java/com/xxx/order/OrderServiceTest.java
❌ 把测试类放到 com.xxx.test 混合大包里，命名 TestOrder
```

- 测试必须是可重复执行的、不受外部环境影响的；不依赖于执行顺序。

```java
❌ 测试类共享一个 static Order 订单对象，方法 A 修改状态后方法 B 依赖该状态才能通过

✅ 每个 @Test 方法内自行构造全新的 Order 对象与依赖
```

- 使用断言（如 AssertJ / JUnit Assertions）校验结果，禁止用 `System.out` 打印人工比对。

```java
❌ System.out.println(order.getStatus());

✅ assertEquals(OrderStatus.PAID, order.getStatus());
```

- 对领域对象的业务规则必须有正例与边界用例（空值、极值、非法值）。

```java
✅ @Test
  public void testRefund_refundableOrder_returnsTrue() { ... }

  @Test
  public void testRefund_paidThenClosed_returnsFalse() { ... }   // 边界：已关闭订单不可退款

  @Test
  public void testRefund_nullOrder_throwsException() { ... }     // 边界：空值
❌ 只写一条"正常订单能退款"的用例
```

## 代码布局与注释规范

- 按业务含义组织代码，相同含义的代码组成一个代码块，不同代码块之间使用一个空行分隔；同一代码块内部保持紧凑，不添加无意义空行。

```java
❌ validate(a);
          // 无意义空行
  validate(b);

  ✅ // 参数校验
     validateOrderParams(cmd);
     validateUserState(userId);

     // 订单落库
     Order order = buildOrder(cmd);
     orderDao.insert(order);
```

- 新建的类、接口和枚举上方使用 JavaDoc 注释 `/** ... */`，优先用一句中文说明其职责，不使用普通块注释或行注释替代。

```java
❌ // 订单领域服务
  public class OrderService { }

  ✅ /** 订单领域服务，负责订单创建、支付与退款的核心业务规则 */
  public class OrderService { }
```

- 方法上方使用 JavaDoc 注释 `/** ... */`，用一句中文说明方法职责；包括 `private` 方法及重写方法。

```java
❌ // 创建订单
  public Long createOrder(CreateOrderCmd cmd) { }

  ✅ /** 根据下单命令创建订单并返回订单号 */
  public Long createOrder(CreateOrderCmd cmd) { }
```

- 方法内部按业务含义分组，在每组相同含义代码的上方使用 `// ...` 添加一句中文注释，说明该组代码的业务意图；不逐行注释，不复述代码语法。

```java
❌ // 定义变量
  Long userId = cmd.getUserId();        // 复述代码语法，无信息量

  ✅ // 校验用户与订单状态
     checkUserState(userId);
     checkOrderPaid(orderId);

     // 计算退款金额
     BigDecimal refundAmount = calculateRefundAmount(order);
```

- 当 `// ...` 注释用于开启新的语义代码组，且前面已有代码时，优先在注释前保留一个空行；注释位于方法、分支、循环、`try` 或 `catch` 代码块开头时，不额外添加空行；不得连续添加多个空行。

```java
  ✅ if (paid) {
          // 已支付订单走退款流程      // 位于代码块开头，注释前不加空行
          doRefund(order);
      }

  ✅ doSave(order);

      // 发送通知                  // 前面已有代码，注释前保留一个空行
      notifyUser(order);

❌ doSave(order);
      // 发送通知


      notifyUser(order);           // 连续多个空行
```

- 所有类注释、方法注释和方法内注释优先使用一句话表达，保持简洁准确，结尾不添加句号、分号、逗号、冒号等标点符号。

```java
❌ /** 该方法主要用于创建订单。请注意：调用前必须校验用户状态！ */

✅ /** 根据下单命令创建订单并返回订单号 */
```

- 注释必须与代码行为一致；修改代码时同步更新注释，不保留误导性注释。

```java
❌ /** 仅支持微信支付 */          // 实际代码已同时支持微信与支付宝
  public PayChannel detect(...) { }

✅ /** 根据渠道配置返回当前支持的支付方式 */
  public PayChannel detect(...) { }
```

- 修改他人代码时，保留表明代码归属与变更背景的注释（如 `@author`、需求编号）。

```java
❌ // 修改时把原 @author zhangsan 与需求编号注释整段删除

✅ /**
   * 优惠券核销规则 2024-09 需求 #4512 调整为按实付金额满减
   * @author zhangsan
   */
```

## 阿里巴巴规约详版（Java 开发手册·嵩山版核心规约）

本节为编码规约全集，编码前通读，编码中按需检索关键词：`命名`、`常量`、`集合`、`并发`、`控制语句`、`异常`、`日志`、`单元测试`、`安全`、`MySQL`、`工程结构`。

### 编程规约

#### 命名

- 代码中任何命名禁止使用拼音与英文混合，杜绝不规范的缩写；避免望文不知义。
- 类名使用 `UpperCamelCase`；方法名、变量名、参数名、成员变量、局部变量使用 `lowerCamelCase`。
- 常量名全大写，单词间下划线分隔，语义完整清晰。
- 抽象类以 `Abstract` 或 `Base` 开头；异常类以 `Exception` 结尾；测试类以被测类名开头、以 `Test` 结尾。
- 类型与中括号紧挨：`int[] arr`，不写 `int arr[]`。
- POJO 类中布尔类型变量不加 `is` 前缀，避免部分框架反序列化错误。

```java
❌ int arr[] = new int[10];
❌ private boolean isSuccess;   // POJO 布尔字段加 is 前缀

✅ int[] arr = new int[10];
✅ private boolean success;     // getter 为 isSuccess()
```

- 包名统一小写，点分隔符之间仅有一个自然语义单词。
- 类名与文件名禁止不规范的随意截断缩写：`AbstractClass` 缩写成 `AbsClass`、`condition` 缩写成 `condi` 均禁止。
- 变量命名允许约定俗成的缩写（`msg`、`info`、`config`、`cnt`、`addr`、`btn` 等，一眼可识别业务含义即可），但禁止 `a`、`b`、`c`、`o`、`t`、`temp` 等无语义命名（见前文正反例）；循环变量与泛型参数 `i`、`s`、`T`、`K`、`V` 属于惯例例外。

#### 常量

- 不允许魔法值直接出现在代码中（见前文正反例）。
- `long` 赋值使用大写 `L`（见前文正反例）。
- 不要使用一个常量类维护所有常量，按功能归类、分开维护。

```
✅ Constants 按域拆分：OrderConstants、PayConstants、RedisKeyConstants
❌ 一个 Constants 类塞 500 个互不相关的常量
```

#### 代码格式与 OOP

- 单个方法总行数不超过 80 行；缩进使用 4 个空格，禁止 tab。
- 不同逻辑、不同语义、不同业务的代码之间插入一个空行。
- 避免通过一个类的对象引用来访问此类的静态变量或静态方法。

```java
❌ new OrderUtils().parse(json);   // OrderUtils.parse 是静态方法
✅ OrderUtils.parse(json);
```

- Object 的 `equals` 方法容易抛空指针，应使用常量或确定有值的对象调用；优先使用 `Objects.equals`。

```java
❌ param.equals("PAID");
✅ "PAID".equals(param);
✅ Objects.equals(oldStatus, newStatus);
```

- 所有整型包装类对象之间值的比较，全部使用 `equals`，不用 `==`。

```java
❌ if (order.getStatus() == oldOrder.getStatus()) { ... }        // Integer 缓存区间外必错
✅ if (Objects.equals(order.getStatus(), oldOrder.getStatus())) { ... }
```

- 任何货币金额均以最小货币单位且整型类型存储；浮点数判断相等不用 `==`。
- 使用 `BigDecimal` 且指定构造参数为字符串；等值比较使用 `compareTo`，不用 `equals`。

```java
❌ new BigDecimal(0.1);                      // 精度丢失
❌ new BigDecimal("0.10").equals(new BigDecimal("0.1"));   // false

✅ new BigDecimal("0.1");
✅ new BigDecimal("0.10").compareTo(new BigDecimal("0.1")) == 0;   // true
```

- 定义 DO/DTO/VO 等 POJO 类时，不设定任何属性默认值。
- 构造方法里禁止加入业务逻辑；复杂初始化放在 `init` 方法。
- POJO 类必须写 `toString`；继承 POJO 时先 `super.toString()`。
- 禁止在 POJO 类中同时存在对应属性 `xxx` 的 `isXxx()` 和 `getXxx()`。
- 使用 `String.split` 结果按索引访问时，先判 `length`，防 `ArrayIndexOutOfBoundsException`。
- 循环体内禁止用 `+` 拼接字符串，改用 `StringBuilder.append`；多线程场景用 `StringBuffer`。

```java
❌ String result = "";
  for (String item : list) { result += item; }

✅ StringBuilder sb = new StringBuilder();
  for (String item : list) { sb.append(item); }
```

- 明确不可变语义时使用 `final` 声明类、成员变量、方法及本地变量。

#### 集合处理

- `hashCode` 与 `equals` 配套重写：重写 `equals` 必须重写 `hashCode`；Set 元素、Map 的 key 必须重写。

```
✅ Order 作为 HashMap 的 key，同时重写 equals 与 hashCode（按 orderId）
❌ Order 只重写 equals 不重写 hashCode，放入 HashSet 后去重失效
```

- 注意 `ArrayList.remove(int index)` 与 `remove(Object o)` 重载混淆。

```java
❌ list.remove(1);          // 本意是删值为 1 的元素，实际删了下标 1
✅ list.remove(Integer.valueOf(1));
```

- `foreach` 循环里禁止对元素进行 `remove`/`add` 操作；删除元素用 `Iterator` 或并发容器。

```java
❌ for (Order o : orders) { if (o.isClosed()) { orders.remove(o); } }   // ConcurrentModificationException

✅ Iterator<Order> it = orders.iterator();
  while (it.hasNext()) { if (it.next().isClosed()) { it.remove(); } }
```

- 集合初始化时指定初始容量：`new HashMap<>(expectedSize / 0.75 + 1)`。

```java
❌ Map<Long, Order> map = new HashMap<>();          // 放 1000 条，反复扩容
✅ Map<Long, Order> map = new HashMap<>(1024 / 0.75 + 1);
```

- 遍历 `entrySet` 而非 `keySet` 遍历 Map，避免一次遍历两次查找。

```java
❌ for (Long key : map.keySet()) { Order o = map.get(key); ... }
✅ for (Map.Entry<Long, Order> entry : map.entrySet()) { ... }
```

- 使用 `Map.isEmpty()` 判空而非 `size() == 0`。
- 高度注意 Map 类集合 K/V 能否存储 null：`HashMap` 的 K/V 都可为 null；`TreeMap` 的 K 不可为 null、V 可为 null；`ConcurrentHashMap` 的 K/V 都不可为 null。
- 合理利用 `computeIfAbsent`、`getOrDefault` 简化代码。

```java
❌ List<Order> list = map.get(uid);
  if (list == null) { list = new ArrayList<>(); map.put(uid, list); }
  list.add(order);

✅ map.computeIfAbsent(uid, k -> new ArrayList<>()).add(order);
```

- 泛型通配符遵循 PECS 原则：`<? extends T>` 用于读取，`<? super T>` 用于写入。
- 禁止使用无泛型限制的原始类型集合。
- 集合转数组使用 `toArray(T[] array)`，传入类型完全一致且长度为 `list.size()`。

```java
❌ String[] arr = (String[]) list.toArray();
✅ String[] arr = list.toArray(new String[list.size()]);
```

- `Arrays.asList()` 转换的集合不支持 `add`/`remove`/`clear`，仅作只读使用。

```java
❌ List<String> list = Arrays.asList("a", "b"); list.add("c");   // UnsupportedOperationException
✅ List<String> list = new ArrayList<>(Arrays.asList("a", "b"));
```

#### 并发处理

- 获取单例对象保证线程安全；方法中共用对象（如 `SimpleDateFormat`）也需保证线程安全。

```java
❌ private static final SimpleDateFormat SDF = new SimpleDateFormat("yyyy-MM-dd");   // 多线程格式化错乱

✅ private static final DateTimeFormatter DTF = DateTimeFormatter.ofPattern("yyyy-MM-dd");
✅ private static final ThreadLocal<SimpleDateFormat> SDF = ThreadLocal.withInitial(...);
```

- 创建线程或线程池时指定有业务意义的名称，便于回溯。

```java
❌ new Thread(() -> ...).start();

✅ new Thread(runnable, "order-refund-worker").start();
```

- 线程资源通过线程池提供，不在应用中自行显式创建 `Thread`；优先使用 `ThreadPoolExecutor` 手动创建并声明饱和策略，不用 `Executors` 快捷方法。

```java
❌ Executors.newFixedThreadPool(10);    // 无界队列可能 OOM

✅ new ThreadPoolExecutor(4, 8, 60L, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(200), new ThreadFactoryBuilder().setNameFormat("order-pool-%d").build(),
        new ThreadPoolExecutor.AbortPolicy());
```

- 必须回收自定义的 `ThreadLocal`，尤其在线程池场景下用完即 `remove`。

```java
❌ ThreadLocal<UserContext> ctx = ...; ctx.set(user); /* 用完不清 */

✅ try { ctx.set(user); doBiz(); } finally { ctx.remove(); }
```

- 高并发时同步调用应考量锁的性能：能用无锁数据结构（如 `ConcurrentHashMap`）就不用锁，能锁区块就不锁整个方法体，能用对象锁就不用类锁。
- 对多行数据库操作必须使用事务；多条写操作要么同时成功要么同时回滚。
- 双重检查锁实现延迟初始化时，目标属性必须声明为 `volatile`。
- HashMap 在多线程下扩容可能形成环形链表导致 CPU 飙升，多线程场景使用 `ConcurrentHashMap`。

#### 控制语句

- switch 块内每个 case 要么通过 `break`/`return` 终止，要么注释说明穿透；必须包含 `default` 且置于末尾。
- switch 括号内变量类型为 String 且为 null 时会 NPE，先判空。
- 在 `if`/`else`/`for`/`while`/`do` 语句中必须使用大括号 `{}`，即使只有一行代码。

```java
❌ if (paid) doRefund();

✅ if (paid) {
      doRefund();
  }
```

- 三目运算符注意自动拆箱 NPE：条件表达式两个分支类型不一致时，包装类型拆箱可能 NPE。

```java
❌ int code = condition ? Integer.valueOf(1) : new Integer(2);   // 拆箱叠加 NPE 风险
✅ int code = condition ? 1 : 2;
```

- 表达异常分支时少用 if-else，可提前 return 或抛出异常；超过 3 层的 if-else 逻辑用卫语句、策略模式、状态模式实现。
- 不要在条件判断中执行复杂逻辑；不要在循环中频繁调用同步方法或远程方法。

```java
❌ for (Order o : orders) { if (checkRemote(o.getId())) { ... } }    // 循环里调 RPC

✅ Set<Long> ids = orders.stream().map(Order::getId).collect(Collectors.toSet());
  Set<Long> validIds = batchCheckRemote(ids);
```

### 异常和日志规约

- 可通过预检查规避的 `RuntimeException`（NPE、IndexOutOfBounds 等）不应通过 catch 处理，应在调用前校验。
- 异常不要用来做流程控制、条件判断（见前文正反例）。
- try 块中尽量放最少代码，不要大段包裹业务逻辑。
- 捕获异常是为了处理它；不要捕获了什么都不做；向更高层抛出时必须保留原始异常作为 cause。

```java
❌ catch (SQLException e) { throw new BizException("订单保存失败"); }          // 丢失原堆栈

✅ catch (SQLException e) {
      throw new BizException("订单保存失败", e);
  }
```

- finally 块必须对资源对象、流对象进行关闭（推荐 try-with-resources）；finally 中不要 return。

```java
❌ InputStream in = null;
  try { in = new FileInputStream(f); ... } finally { if (in != null) { try { in.close(); } catch (IOException e) { } } }   // 关闭又吞异常

✅ try (InputStream in = new FileInputStream(f)) {
      ...
  }
```

- 不要在循环体中捕获异常，应移到循环体外（除非有明确理由）。
- 防 NPE：数据库取出的字段可能为 null，远程调用返回对象、集合元素都可能为 null，使用前判断（见前文工具约定正反例）。
- 日志使用 SLF4J 门面 + 占位符，禁止字符串拼接（见前文正反例）。
- 异常信息应包括问题发生的上下文与关键数据。
- 避免重复打日志；生产环境禁止 debug 日志，有选择地输出 info，用 warn 记录可恢复异常。

### 单元测试规约

- AIR 原则：Automatic（自动化）、Independent（独立性）、Repeatable（可重复）。
- BCDE 原则：Border（边界值）、Correct（正确输入）、Design（文档化）、Error（错误输入）。
- 测试粒度到方法级别；单个用例方法体保持精简。
- 运行结果稳定：含随机值时先固定随机种子。

```java
❌ new Random().nextInt(100) 直接用于断言

✅ Random random = new Random(42);   // 固定种子，结果可复现
```

- 代码变更后先跑测试；增量代码分支覆盖率目标 ≥ 70%。
- 测试类与被测类同包；方法命名 `test方法名_条件_期望结果`（见前文正反例）。

### 安全规约

- 隶属于用户个人的页面或功能必须进行权限校验。

```
✅ 查询订单详情前校验 order.getUserId() 与当前登录用户一致
❌ 只凭前端传入的 orderId 直接返回订单数据
```

- 用户敏感数据（手机号、身份证、银行卡号）禁止直接展示完整明文，展示时脱敏。

```java
❌ return user.getMobile();                  // 13812345678 原样返回

✅ return DesensitizeUtil.mobile(user.getMobile());   // 138****5678
```

- SQL 参数严格使用参数绑定（`?` 或 PreparedStatement），严禁字符串拼接 SQL。

```java
❌ String sql = "select * from t_user where name = '" + name + "'";
✅ String sql = "select * from t_user where name = ?";
```

- 用户请求传入的任何参数必须做有效性校验（类型、长度、范围、格式）。
- 禁止反序列化不可信数据（fastjson 需开启 safeMode 或升级至安全版本）。
- 表单、AJAX 提交必须执行 CSRF 安全过滤。
- 使用平台资源（短信、邮件、支付）时，必须实现防重放与频率限制。

### MySQL 数据库规约

- 表达是否概念的字段用 `is_xxx`（unsigned tinyint，1 是 0 否）；POJO 中对应字段不加 is 前缀。
- 索引命名：主键 `pk_字段名`、唯一 `uk_字段名`、普通 `idx_字段名`。
- 小数类型用 `decimal`，禁止 `float`/`double`；长度几乎不变的字符串用 `char`。
- `varchar` 长度按实际需要分配，不超 5000；更长用 `text` 并独立表存储。
- 表必备三字段：`id`（unsigned bigint 自增）、`create_time`、`update_time`。
- 不得使用外键与级联，一切外键概念在应用层解决；禁止使用存储过程；禁止 `select *`。

```sql
❌ select * from t_order where id = ?;
✅ select id, user_id, amount, status from t_order where id = ?;
```

- `count(distinct col)` 多列时注意除法算分母；`count(col)` 不统计 null 行，`count(*)` 为 SQL92 标准。
- 判断 null 用 `is null` / `is not null`，不用 `= null`。
- 分页 limit 起始与条数必须为非负整数；深度翻页用游标或子查询优化。
- SQL 中 `in` 操作控制在 1000 个元素以内。
- 事务中避免大 RPC 调用；大事务拆分，避免长事务锁表。

### 工程结构规约

- 应用分层：Web 层（Controller）只做参数校验与结果转换；Service 层做业务编排；Manager 层做通用处理与第三方封装；DAO 层数据访问；领域层放领域模型与领域服务。
- DO（数据对象）、DTO（传输对象）、VO（展示对象）严格区分，转换职责清晰，禁止混用。

```
✅ Controller 返回 OrderVO，Service 入参出参用 OrderDTO，DAO 出参用 OrderDO
❌ 一个 Order 类从 Controller 一路用到 SQL 映射，字段混杂展示与持久化职责
```

- 引入新依赖须确认版本与冲突；废弃的类不删除，用 `@Deprecated` 标注并说明替代方案。

```java
❌ 直接删除还在被引用的旧工具类

✅ /** 已废弃，请使用 OrderQueryUtils {@link OrderQueryUtils} */
  @Deprecated
  public class OrderOldUtils { ... }
```

- 服务器 JVM 参数需结合实际压测设定，不盲目照抄。

## 交付检查

交付前逐项确认：已识别项目架构风格且新代码已归位到相应层与包，未擅自另设层次；风格基准已对照已有实现确定；未使用 `var`、`record`、箭头 switch、文本块、`List.of`、`.toList()` 等任何 Java 8 之后的新语法或新 API，类型均为显式声明；POJO 已优先使用 Lombok 注解生成存取方法，无手写大量 getter/setter，继承场景已加 `@EqualsAndHashCode(callSuper = true)`；DDD 项目中固定取值集合均使用枚举类型且复用了已有枚举，依赖方向未被破坏；已复用项目工具类，指定工具类已用于全部对应场景；无魔法值；命名符合规约；方法行数与参数数量达标；空值与异常路径均以卫语句前置提前返回，正常逻辑保持顶层零嵌套；Stream 保持简单；异常未被吞掉、未用于流程控制；日志格式符合 `{类}-{方法}-{备注}` 且无敏感信息；单元测试已编写且覆盖正例与边界；注释规范全部满足；验证结果已报告。
