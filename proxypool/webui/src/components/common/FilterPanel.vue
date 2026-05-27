<template>
  <div class="filter-panel">
    <div class="filter-panel-header">
      <h4 class="filter-panel-title">
        <slot name="title">筛选条件</slot>
      </h4>
      <button
        v-if="showClearButton"
        class="btn btn-xs btn-ghost"
        @click="$emit('clear')"
      >
        清空筛选
      </button>
    </div>
    <div class="filter-panel-body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="filter-panel-footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  showClearButton: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['clear'])
</script>

<style scoped>
.filter-panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 12px 16px;
}

.filter-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.filter-panel-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0;
}

.filter-panel-body {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-panel-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}
</style>
