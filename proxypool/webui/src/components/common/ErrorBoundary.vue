<template>
  <div v-if="error" class="error-boundary">
    <div class="error-boundary-content">
      <div class="error-boundary-icon">⚠️</div>
      <h3 class="error-boundary-title">组件加载失败</h3>
      <p class="error-boundary-message">{{ error.message || '发生未知错误' }}</p>
      <button class="btn btn-secondary" @click="retry">重试</button>
    </div>
  </div>
  <slot v-else />
</template>

<script>
export default {
  name: 'ErrorBoundary',
  props: {
    pageName: {
      type: String,
      default: '页面',
    },
  },
  data() {
    return {
      error: null,
    };
  },
  errorCaptured(err, vm, info) {
    this.error = err;
    console.error(`[ErrorBoundary] ${this.pageName} error:`, err, info);
    return false;
  },
  methods: {
    retry() {
      this.error = null;
      this.$forceUpdate();
    },
  },
};
</script>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 24px;
}

.error-boundary-content {
  text-align: center;
  max-width: 400px;
}

.error-boundary-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-boundary-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px;
}

.error-boundary-message {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 16px;
}
</style>
