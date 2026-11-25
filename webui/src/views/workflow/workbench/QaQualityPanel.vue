<script lang="ts" setup>
import { computed, ref } from 'vue';

import {
  Button,
  Card,
  Empty,
  Modal,
  Progress,
  Segmented,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import type { TaskInsights } from '#/api/workflow';

import { renderMarkdown } from '#/utils/markdown';

type CaseRow = NonNullable<
  NonNullable<TaskInsights['release_confidence']>['rows']
>[number];

const props = defineProps<{
  insights: TaskInsights | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  approve: [status: 'approved' | 'pending'];
  preview: [nodeId: string];
}>();

const caseFilter = ref<'all' | 'fail' | 'other' | 'pass'>('all');

const confidence = computed(() => props.insights?.release_confidence ?? null);
const qa = computed(() => props.insights?.qa_review ?? null);
const rows = computed(() => confidence.value?.rows ?? []);
const issues = computed(() => confidence.value?.issues ?? []);

const confidencePercent = computed(() => {
  const score = confidence.value?.score;
  if (score == null || Number.isNaN(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
});

const confidenceColor = computed(() => {
  const reached = confidence.value?.reached_0_8;
  if (reached === true) return '#52c41a';
  if (reached === false) return '#faad14';
  return '#1677ff';
});

const counts = computed(() => {
  const summary = { pass: 0, skip: 0, fail: 0, blocked: 0, other: 0 };
  for (const row of rows.value) {
    const key = row.result as keyof typeof summary;
    summary[key] = (summary[key] ?? 0) + 1;
  }
  return summary;
});

const totalCases = computed(() => rows.value.length);

const filteredRows = computed(() => {
  if (caseFilter.value === 'all') return rows.value;
  if (caseFilter.value === 'fail') {
    return rows.value.filter((r) => r.result === 'fail' || r.result === 'blocked');
  }
  if (caseFilter.value === 'pass') return rows.value.filter((r) => r.result === 'pass');
  return rows.value.filter((r) => !['pass', 'fail', 'blocked'].includes(r.result));
});

const qaTagColor = computed(() => {
  const status = qa.value?.status;
  if (status === 'approved') return 'success';
  if (status === 'pending') return 'warning';
  return 'default';
});

const qaTagText = computed(() => {
  const status = qa.value?.status;
  if (status === 'approved') return 'QA 已通过';
  if (status === 'pending') return 'QA 待审';
  if (status === 'missing') return '未找到用例文档';
  return '未检测';
});

function resultColor(result: string) {
  if (result === 'pass') return 'success';
  if (result === 'fail') return 'error';
  if (result === 'blocked') return 'warning';
  if (result === 'skip') return 'default';
  return 'default';
}

function issueColor(level: string) {
  if (level === 'fail') return 'error';
  if (level === 'blocked') return 'warning';
  return 'blue';
}

const caseColumns = [
  { title: '用例', dataIndex: 'id', width: 130 },
  { title: '名称', dataIndex: 'name', ellipsis: true },
  { title: '类型', dataIndex: 'case_type', width: 76 },
  { title: '优先级', dataIndex: 'priority', width: 76 },
  { title: '结果', dataIndex: 'result', width: 90 },
];

const activeCase = ref<CaseRow | null>(null);
const caseDetailOpen = ref(false);
const basisOpen = ref(false);

function openCase(record: CaseRow) {
  activeCase.value = record;
  caseDetailOpen.value = true;
}

const caseDetailHtml = computed(() => {
  const detail = activeCase.value?.detail?.trim();
  if (!detail) return '';
  return renderMarkdown(detail);
});

const basisHtml = computed(() => {
  const basis = confidence.value?.basis?.trim();
  if (!basis) return '';
  return renderMarkdown(basis);
});
</script>

<template>
  <div class="qa-panel flex h-full min-h-0 flex-col gap-3 overflow-y-auto pr-1">
    <Empty
      v-if="!insights"
      description="选择任务后查看 QA 质量"
      :image-style="{ height: 40 }"
    />

    <template v-else>
      <!-- 概览：置信度 + 用例统计 + 审批动作 -->
      <div class="grid gap-3 lg:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
        <Card class="shrink-0" size="small" title="发布置信度">
          <div class="flex flex-col items-center gap-1">
            <Progress
              :percent="confidencePercent"
              :stroke-color="confidenceColor"
              type="dashboard"
              :width="120"
            />
            <Tag
              v-if="confidence?.reached_0_8 != null"
              :color="confidence.reached_0_8 ? 'success' : 'warning'"
              class="m-0"
            >
              {{ confidence.reached_0_8 ? '已达 0.8 阈值' : '未达 0.8 阈值' }}
            </Tag>
            <span v-else class="text-xs opacity-40">报告中未解析到置信度</span>
            <Button
              v-if="confidence?.basis"
              class="mt-1"
              size="small"
              type="link"
              @click="basisOpen = true"
            >
              查看评分依据
            </Button>
            <Button
              v-if="confidence?.file"
              size="small"
              type="link"
              @click="emit('preview', 'verify_tests')"
            >
              打开测试报告
            </Button>
            <span v-else class="text-xs opacity-40">尚无 05-test-report.md</span>
          </div>
        </Card>

        <Card class="min-w-0" size="small" title="质量概览">
          <div class="flex flex-wrap items-center gap-2">
            <Tag :color="qaTagColor" class="m-0">{{ qaTagText }}</Tag>
            <Tooltip title="QA 为异步审批，不阻塞流水线">
              <Tag class="m-0" color="default">异步 · 不阻塞</Tag>
            </Tooltip>
            <Tag
              v-if="confidence?.test_passed != null"
              :color="confidence.test_passed ? 'success' : 'error'"
              class="m-0"
            >
              test_passed={{ confidence.test_passed }}
            </Tag>
            <Button
              v-if="qa?.status === 'pending'"
              :loading="loading"
              size="small"
              type="primary"
              @click="emit('approve', 'approved')"
            >
              标记用例 QA 通过
            </Button>
            <Button
              v-if="qa?.status === 'approved'"
              :loading="loading"
              size="small"
              @click="emit('approve', 'pending')"
            >
              重置为待审
            </Button>
            <Button v-if="qa?.file" size="small" type="link" @click="emit('preview', 'design_test_cases')">
              打开测试用例
            </Button>
          </div>

          <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div class="qa-kpi">
              <div class="qa-kpi__value">{{ totalCases }}</div>
              <div class="qa-kpi__label">用例总数</div>
            </div>
            <div class="qa-kpi qa-kpi--pass">
              <div class="qa-kpi__value">{{ counts.pass }}</div>
              <div class="qa-kpi__label">通过</div>
            </div>
            <div class="qa-kpi qa-kpi--fail">
              <div class="qa-kpi__value">{{ counts.fail + counts.blocked }}</div>
              <div class="qa-kpi__label">失败 / 阻塞</div>
            </div>
            <div class="qa-kpi qa-kpi--skip">
              <div class="qa-kpi__value">{{ counts.skip }}</div>
              <div class="qa-kpi__label">跳过</div>
            </div>
          </div>

          <div v-if="qa?.user_note" class="mt-3 text-xs opacity-60">
            备注：{{ qa.user_note }}
          </div>
          <ul
            v-if="confidence?.highlights?.length"
            class="mt-3 mb-0 list-disc pl-4 text-xs opacity-60"
          >
            <li v-for="(line, idx) in confidence.highlights" :key="idx">
              {{ line }}
            </li>
          </ul>
        </Card>
      </div>

      <!-- 质量问题 -->
      <Card size="small">
        <template #title>
          <span>质量问题</span>
          <Tag class="ml-2 m-0" :color="issues.length ? 'warning' : 'success'">
            {{ issues.length }}
          </Tag>
        </template>
        <div v-if="!issues.length" class="py-3 text-center text-xs opacity-50">
          没有未通过的用例，也没有报告问题项
        </div>
        <ul v-else class="m-0 flex list-none flex-col gap-2 p-0">
          <li
            v-for="(item, idx) in issues"
            :key="`${item.source}-${idx}`"
            class="qa-issue"
          >
            <Tag :color="issueColor(item.level)" class="m-0 shrink-0">
              {{ item.level === 'note' ? '报告' : item.level }}
            </Tag>
            <span class="min-w-0 flex-1 text-xs leading-5">{{ item.text }}</span>
          </li>
        </ul>
      </Card>

      <!-- 用例明细 -->
      <Card size="small">
        <template #title>
          <span>用例明细</span>
          <Tag class="ml-2 m-0">{{ filteredRows.length }}</Tag>
        </template>
        <template #extra>
          <Segmented
            v-model:value="caseFilter"
            :options="[
              { label: `全部 ${totalCases}`, value: 'all' },
              { label: `失败 ${counts.fail + counts.blocked}`, value: 'fail' },
              { label: `跳过 ${counts.skip}`, value: 'other' },
              { label: `通过 ${counts.pass}`, value: 'pass' },
            ]"
            size="small"
          />
        </template>
        <Table
          :columns="caseColumns"
          :data-source="filteredRows"
          :pagination="
            filteredRows.length > 12
              ? { pageSize: 12, size: 'small', showSizeChanger: false }
              : false
          "
          :custom-row="
            (record) => ({
              onClick: () => openCase(record as CaseRow),
              class: 'qa-case-row',
            })
          "
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'id'">
              <Button class="qa-case-link" size="small" type="link" @click.stop="openCase(record as CaseRow)">
                {{ record.id }}
              </Button>
            </template>
            <template v-else-if="column.dataIndex === 'name'">
              <span v-if="record.name" class="text-xs">{{ record.name }}</span>
              <span v-else class="text-xs opacity-40">用例文档中无此条</span>
            </template>
            <template v-else-if="column.dataIndex === 'case_type'">
              <Tag v-if="record.case_type" class="m-0">{{ record.case_type }}</Tag>
              <span v-else class="opacity-30">—</span>
            </template>
            <template v-else-if="column.dataIndex === 'priority'">
              <span v-if="record.priority" class="text-xs">{{ record.priority }}</span>
              <span v-else class="opacity-30">—</span>
            </template>
            <template v-else-if="column.dataIndex === 'result'">
              <Tag :color="resultColor(record.result)" class="m-0">
                {{ record.result }}
              </Tag>
            </template>
          </template>
          <template #emptyText>
            <Empty
              description="未解析到用例结果表，查看 05-test-report.md 末尾"
              :image-style="{ height: 36 }"
            />
          </template>
        </Table>
      </Card>

      <!-- 用例详情 -->
      <Modal
        v-model:open="caseDetailOpen"
        :footer="null"
        :title="activeCase ? `${activeCase.id} ${activeCase.name || ''}` : '用例详情'"
        width="720px"
      >
        <div v-if="activeCase" class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <Tag :color="resultColor(activeCase.result)" class="m-0">
              {{ activeCase.result }}
            </Tag>
            <Tag v-if="activeCase.case_type" class="m-0">{{ activeCase.case_type }}</Tag>
            <Tag v-if="activeCase.priority" class="m-0">优先级 {{ activeCase.priority }}</Tag>
            <Tag v-if="activeCase.auto" class="m-0">可自动执行 {{ activeCase.auto }}</Tag>
          </div>

          <div v-if="caseDetailHtml" class="qa-case-detail" v-html="caseDetailHtml"></div>
          <div v-else class="rounded border border-border/40 p-3 text-xs opacity-60">
            测试用例文档里没有该用例的明细章节（可能只在报告结果表中出现）。
          </div>

          <div class="flex justify-end gap-2">
            <Button size="small" @click="emit('preview', 'design_test_cases')">
              打开测试用例文档
            </Button>
            <Button size="small" @click="emit('preview', 'verify_tests')">
              打开测试报告
            </Button>
          </div>
        </div>
      </Modal>

      <!-- 置信度评分依据：走弹窗，避免在滚动容器里挤压表格 -->
      <Modal
        v-model:open="basisOpen"
        :footer="null"
        title="置信度评分依据"
        width="760px"
      >
        <div v-if="basisHtml" class="qa-basis" v-html="basisHtml"></div>
        <div v-else class="text-xs opacity-60">报告中未找到置信度评估章节。</div>
      </Modal>
    </template>
  </div>
</template>

<style scoped>
.qa-kpi {
  border: 1px solid hsl(var(--border) / 40%);
  border-radius: 6px;
  padding: 8px 10px;
  background: hsl(var(--muted) / 25%);
}

.qa-kpi__value {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.2;
}

.qa-kpi__label {
  font-size: 11px;
  opacity: 0.55;
  margin-top: 2px;
}

.qa-kpi--pass .qa-kpi__value {
  color: #52c41a;
}

.qa-kpi--fail .qa-kpi__value {
  color: #ff4d4f;
}

.qa-kpi--skip .qa-kpi__value {
  color: #8c8c8c;
}

.qa-issue {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid hsl(var(--border) / 40%);
  border-radius: 6px;
  padding: 6px 8px;
}

:deep(.qa-case-row) {
  cursor: pointer;
}

.qa-case-link {
  height: auto;
  padding: 0;
  font-family: var(--font-mono, ui-monospace, monospace);
}

.qa-case-detail {
  max-height: 46vh;
  overflow: auto;
  font-size: 13px;
  line-height: 1.7;
  padding-right: 4px;
}

.qa-case-detail :deep(ul) {
  margin: 0;
  padding-left: 18px;
}

.qa-case-detail :deep(code) {
  background: hsl(var(--muted) / 60%);
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 12px;
}

.qa-basis {
  max-height: 62vh;
  overflow: auto;
  font-size: 13px;
  line-height: 1.7;
  padding-right: 4px;
}

.qa-basis :deep(h2),
.qa-basis :deep(h3) {
  font-size: 14px;
  font-weight: 600;
  margin: 14px 0 6px;
}

.qa-basis :deep(h2:first-child),
.qa-basis :deep(h3:first-child) {
  margin-top: 0;
}

.qa-basis :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 8px 0;
}

.qa-basis :deep(th),
.qa-basis :deep(td) {
  border: 1px solid hsl(var(--border) / 50%);
  padding: 4px 8px;
  text-align: left;
  vertical-align: top;
}

.qa-basis :deep(th) {
  background: hsl(var(--muted) / 40%);
  font-weight: 600;
}

.qa-basis :deep(ul),
.qa-basis :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.qa-basis :deep(code) {
  background: hsl(var(--muted) / 60%);
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 12px;
}
</style>
