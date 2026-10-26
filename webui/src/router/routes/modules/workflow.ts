import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    name: 'WorkflowRuleDirs',
    path: '/rule-dirs',
    component: () => import('#/views/workflow/rule-dirs/index.vue'),
    meta: {
      icon: 'lucide:book-open',
      order: -1,
      title: $t('page.workflow.ruleDirs'),
    },
  },
  {
    name: 'WorkflowWorkbench',
    path: '/workbench',
    component: () => import('#/views/workflow/workbench/index.vue'),
    meta: {
      affixTab: true,
      icon: 'lucide:workflow',
      order: 0,
      title: $t('page.workflow.workbench'),
    },
  },
];

export default routes;
