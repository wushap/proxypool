<template>
  <nav class="breadcrumb" aria-label="面包屑导航">
    <ol class="breadcrumb-list">
      <li
        v-for="(item, index) in items"
        :key="index"
        class="breadcrumb-item"
        :class="{ 'breadcrumb-item--active': index === items.length - 1 }"
      >
        <a
          v-if="item.path && index < items.length - 1"
          :href="item.path"
          class="breadcrumb-link"
          @click.prevent="handleClick(item)"
        >
          {{ item.label }}
        </a>
        <span v-else class="breadcrumb-text">{{ item.label }}</span>
        <span
          v-if="index < items.length - 1"
          class="breadcrumb-separator"
          aria-hidden="true"
        >
          /
        </span>
      </li>
    </ol>
  </nav>
</template>

<script setup>
const props = defineProps({
  items: {
    type: Array,
    required: true,
    validator: (value) => {
      return value.every(item => item.label && typeof item.label === 'string')
    },
  },
})

const emit = defineEmits(['navigate'])

function handleClick(item) {
  if (item.onClick && typeof item.onClick === 'function') {
    item.onClick()
  }
  emit('navigate', item)
}
</script>

<style scoped>
.breadcrumb {
  padding: 8px 0;
  font-size: 13px;
}

.breadcrumb-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.breadcrumb-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.breadcrumb-link {
  color: var(--muted);
  text-decoration: none;
  transition: color 0.15s ease;
}

.breadcrumb-link:hover {
  color: var(--accent);
  text-decoration: underline;
}

.breadcrumb-text {
  color: var(--ink);
  font-weight: 500;
}

.breadcrumb-item--active .breadcrumb-text {
  color: var(--ink);
  font-weight: 600;
}

.breadcrumb-separator {
  color: var(--muted);
  margin: 0 4px;
}
</style>
