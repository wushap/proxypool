<template>
  <div class="pagination">
    <div class="pagination-info">
      <span class="text-muted">每页</span>
      <select
        :value="perPage"
        class="select input-sm"
        style="width: 56px;"
        @change="$emit('update:perPage', Number($event.target.value))"
      >
        <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
      </select>
      <span class="text-muted">{{ pageIndicator }}</span>
    </div>
    <div class="pagination-nav">
      <slot name="actions" />
      <button
        :disabled="!canPrev"
        class="btn btn-xs btn-ghost"
        @click="$emit('prev')"
      >
        上一页
      </button>
      <button
        :disabled="!canNext"
        class="btn btn-xs btn-ghost"
        @click="$emit('next')"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: {
    type: Number,
    required: true,
  },
  perPage: {
    type: Number,
    required: true,
  },
  total: {
    type: Number,
    required: true,
  },
  canPrev: {
    type: Boolean,
    required: true,
  },
  canNext: {
    type: Boolean,
    required: true,
  },
  pageSizeOptions: {
    type: Array,
    default: () => [10, 50, 100],
  },
})

defineEmits(['update:perPage', 'prev', 'next'])

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(props.total / props.perPage))
})

const pageIndicator = computed(() => {
  return `${props.page}/${totalPages.value} (${props.total})`
})
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  font-size: 13px;
}

.pagination-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
