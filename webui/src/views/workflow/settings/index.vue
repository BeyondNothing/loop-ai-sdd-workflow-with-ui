<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Descriptions,
  Form,
  Radio,
  Space,
  Tag,
} from 'ant-design-vue';

import { useSettings } from './use-settings';

const { defaultTool, loading, save, saving, systemInfo, tools } = useSettings();
</script>

<template>
  <Page auto-content-height content-class="p-4">
    <div class="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 class="text-lg font-medium">系统设置</h2>
        <p class="text-sm opacity-50">
          配置工作流执行时使用的默认 AI 编程工具；任务启动未单独指定时将使用此默认值。
        </p>
      </div>

      <Card :loading="loading" size="small" title="运行环境">
        <Descriptions v-if="systemInfo" :column="2" size="small">
          <Descriptions.Item label="操作系统">
            {{ systemInfo.os_name }}
          </Descriptions.Item>
          <Descriptions.Item label="平台标识">
            {{ systemInfo.platform }}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card :loading="loading" size="small" title="默认 AI 工具">
        <Form layout="vertical">
          <Form.Item label="启动工作流时使用">
            <Radio.Group v-model:value="defaultTool" class="tool-radio-group">
              <Space direction="vertical" class="w-full">
                <Radio
                  v-for="tool in tools"
                  :key="tool.id"
                  :value="tool.id"
                  class="tool-radio"
                >
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ tool.name }}</span>
                    <Tag class="m-0 text-[10px]">{{ tool.id }}</Tag>
                  </div>
                  <div class="text-xs opacity-45">{{ tool.description }}</div>
                </Radio>
              </Space>
            </Radio.Group>
          </Form.Item>
          <div class="flex justify-end">
            <Button :loading="saving" type="primary" @click="save">
              <IconifyIcon class="mr-1" icon="lucide:save" />
              保存配置
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  </Page>
</template>

<style scoped>
.tool-radio-group :deep(.ant-radio-wrapper) {
  align-items: flex-start;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid hsl(var(--border) / 60%);
  border-radius: 8px;
}

.tool-radio-group :deep(.ant-radio-wrapper-checked) {
  border-color: hsl(var(--primary) / 50%);
  background: hsl(var(--primary) / 8%);
}
</style>
