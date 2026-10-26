<script lang="ts" setup>
import { reactive, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Checkbox, Form, Input, Modal, message } from 'ant-design-vue';

import { workflowApi } from '#/api/workflow';

import PathPickerModal from '../workbench/PathPickerModal.vue';

const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ created: [] }>();

const saving = ref(false);
const pickerOpen = ref(false);
const form = reactive({
  name: '',
  folder_path: '',
  create_folder: true,
});

function resetForm() {
  form.name = '';
  form.folder_path = '';
  form.create_folder = true;
}

async function handleOk() {
  if (!form.name.trim()) return message.warning('请填写规则名称');
  if (!form.folder_path.trim()) return message.warning('请选择或输入规则目录');
  saving.value = true;
  try {
    await workflowApi.createRuleSet({
      name: form.name.trim(),
      folder_path: form.folder_path.trim(),
      create_folder: form.create_folder,
    });
    message.success('规则目录已创建');
    open.value = false;
    resetForm();
    emit('created');
  } catch (e) {
    message.error(String(e));
  } finally {
    saving.value = false;
  }
}

function onPicked(path: string) {
  form.folder_path = path;
  pickerOpen.value = false;
}
</script>

<template>
  <Modal
    v-model:open="open"
    :confirm-loading="saving"
    ok-text="创建"
    title="新建规则目录"
    @cancel="resetForm"
    @ok="handleOk"
  >
    <Form layout="vertical">
      <Form.Item label="规则名称" required>
        <Input v-model:value="form.name" placeholder="例如：DDD 设计规范" />
      </Form.Item>
      <Form.Item label="MD 规则目录" required>
        <Input.Group compact>
          <Input
            v-model:value="form.folder_path"
            placeholder="绝对路径或相对 workflow 根目录"
            style="width: calc(100% - 72px)"
          />
          <Button @click="pickerOpen = true">
            <IconifyIcon icon="lucide:folder-open" />
          </Button>
        </Input.Group>
      </Form.Item>
      <Checkbox v-model:checked="form.create_folder">
        目录不存在时自动创建
      </Checkbox>
    </Form>
  </Modal>

  <PathPickerModal
    v-model:open="pickerOpen"
    :initial-path="form.folder_path"
    mode="dir"
    title="选择规则目录"
    @select="onPicked"
  />
</template>
