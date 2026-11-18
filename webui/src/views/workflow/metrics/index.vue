<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
} from 'ant-design-vue';

import { type ProjectBinding, workflowApi } from '#/api/workflow';

const loading = ref(false);
const days = ref(7);
const selectedProjectId = ref<string>('');
const projects = ref<ProjectBinding[]>([]);
const metrics = ref<Awaited<ReturnType<typeof workflowApi.getRunMetrics>> | null>(
  null,
);

const projectOptions = computed(() => [
  { label: '全部项目', value: '' },
  ...projects.value.map((p) => ({
    label: `${p.name} (${p.project_id})`,
    value: p.project_id,
  })),
]);

const dayOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 14 天', value: 14 },
  { label: '近 30 天', value: 30 },
];

function formatMs(ms: number | null | undefined) {
  if (ms == null || Number.isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const min = sec / 60;
  return `${min.toFixed(1)} min`;
}

function statusColor(status: string) {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'cancelled' || status === 'cancelling') return 'warning';
  if (status === 'running' || status === 'queued') return 'processing';
  return 'default';
}

const stuckColumns = [
  { title: '卡点节点', dataIndex: 'node_id' },
  { title: '次数', dataIndex: 'count', width: 100 },
];

const recentColumns = [
  { title: 'Run', dataIndex: 'run_id', width: 120 },
  { title: '状态', dataIndex: 'status', width: 110 },
  { title: '耗时', dataIndex: 'duration_ms', width: 110 },
  { title: '卡点', dataIndex: 'stuck_node', width: 140 },
  { title: '开始时间', dataIndex: 'started_at' },
];

const statusEntries = computed(() =>
  Object.entries(metrics.value?.status_counts || {}).sort((a, b) => b[1] - a[1]),
);

async function loadProjects() {
  const data = await workflowApi.getProjects();
  projects.value = data.projects || [];
}

async function loadMetrics() {
  loading.value = true;
  try {
    metrics.value = await workflowApi.getRunMetrics({
      days: days.value,
      project_id: selectedProjectId.value || undefined,
    });
  } catch (e) {
    metrics.value = null;
    console.error(e);
  } finally {
    loading.value = false;
  }
}

watch([days, selectedProjectId], () => {
  void loadMetrics();
});

onMounted(async () => {
  await loadProjects();
  await loadMetrics();
});
</script>

<template>
  <Page auto-content-height content-class="p-4">
    <div class="mx-auto max-w-6xl space-y-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-medium">运行指标</h2>
          <p class="text-sm opacity-50">近 N 日耗时、失败率与卡点节点（读本地 runs 记录）。</p>
        </div>
        <Space wrap>
          <Select v-model:value="days" :options="dayOptions" class="w-[120px]" />
          <Select
            v-model:value="selectedProjectId"
            :options="projectOptions"
            class="w-[260px]"
            placeholder="全部项目"
          />
          <Button :loading="loading" @click="loadMetrics">
            <IconifyIcon class="mr-1" icon="lucide:refresh-cw" />
            刷新
          </Button>
        </Space>
      </div>

      <Row :gutter="[12, 12]">
        <Col :md="6" :xs="12">
          <Card :loading="loading" size="small">
            <Statistic :value="metrics?.total ?? 0" title="总 runs" />
          </Card>
        </Col>
        <Col :md="6" :xs="12">
          <Card :loading="loading" size="small">
            <Statistic
              :precision="1"
              :value="(metrics?.fail_rate ?? 0) * 100"
              suffix="%"
              title="失败/取消率"
            />
          </Card>
        </Col>
        <Col :md="6" :xs="12">
          <Card :loading="loading" size="small">
            <Statistic
              :value-style="{ fontSize: '20px' }"
              :value="formatMs(metrics?.duration_ms?.p50)"
              title="耗时 P50"
            />
          </Card>
        </Col>
        <Col :md="6" :xs="12">
          <Card :loading="loading" size="small">
            <Statistic
              :value-style="{ fontSize: '20px' }"
              :value="formatMs(metrics?.duration_ms?.p95)"
              title="耗时 P95"
            />
          </Card>
        </Col>
      </Row>

      <Row :gutter="[12, 12]">
        <Col :md="12" :xs="24">
          <Card :loading="loading" size="small" title="状态分布">
            <div v-if="statusEntries.length" class="space-y-2">
              <div
                v-for="[status, count] in statusEntries"
                :key="status"
                class="flex items-center gap-3"
              >
                <Tag :color="statusColor(status)" class="m-0 w-24 text-center">
                  {{ status }}
                </Tag>
                <Progress
                  :percent="
                    metrics?.total
                      ? Math.round((count / metrics.total) * 100)
                      : 0
                  "
                  :show-info="false"
                  class="flex-1"
                  size="small"
                />
                <span class="w-10 text-right text-xs opacity-60">{{ count }}</span>
              </div>
            </div>
            <Empty v-else description="暂无数据" />
          </Card>
        </Col>
        <Col :md="12" :xs="24">
          <Card :loading="loading" size="small" title="卡点节点 Top">
            <Table
              :columns="stuckColumns"
              :data-source="metrics?.stuck_nodes || []"
              :locale="{ emptyText: '暂无失败卡点' }"
              :pagination="false"
              :row-key="(r) => r.node_id"
              size="small"
            />
          </Card>
        </Col>
      </Row>

      <Card :loading="loading" size="small" title="按日趋势">
        <Table
          :columns="[
            { title: '日期', dataIndex: 'date' },
            { title: '总计', dataIndex: 'total', width: 80 },
            { title: '成功', dataIndex: 'completed', width: 80 },
            { title: '失败', dataIndex: 'failed', width: 80 },
            { title: '取消', dataIndex: 'cancelled', width: 80 },
          ]"
          :data-source="metrics?.daily || []"
          :locale="{ emptyText: '暂无按日数据' }"
          :pagination="false"
          :row-key="(r) => r.date"
          size="small"
        />
      </Card>

      <Card :loading="loading" size="small" title="最近 runs">
        <Table
          :columns="recentColumns"
          :data-source="metrics?.recent_runs || []"
          :locale="{ emptyText: '暂无 runs' }"
          :pagination="{ pageSize: 10 }"
          :row-key="(r) => r.run_id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'status'">
              <Tag :color="statusColor(record.status)">{{ record.status }}</Tag>
            </template>
            <template v-else-if="column.dataIndex === 'duration_ms'">
              {{ formatMs(record.duration_ms) }}
            </template>
            <template v-else-if="column.dataIndex === 'stuck_node'">
              {{ record.stuck_node || '—' }}
            </template>
          </template>
        </Table>
      </Card>
    </div>
  </Page>
</template>
