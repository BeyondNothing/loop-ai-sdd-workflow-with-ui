<script lang="ts" setup>
import { computed } from 'vue';

import { BasicLayout, ThemeToggle } from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

const userStore = useUserStore();
const isWorkbench = import.meta.env.VITE_WORKBENCH_NO_AUTH === 'true';

const avatar = computed(
  () => userStore.userInfo?.avatar ?? preferences.app.defaultAvatar,
);
</script>

<template>
  <BasicLayout>
    <template v-if="!isWorkbench" #user-dropdown />
    <template v-else #user-dropdown>
      <div class="flex items-center gap-3 px-3 text-sm text-foreground/80">
        <ThemeToggle />
        <img :src="avatar" alt="" class="size-7 rounded-full" />
        <span>{{ userStore.userInfo?.realName || '操作员' }}</span>
      </div>
    </template>
  </BasicLayout>
</template>
