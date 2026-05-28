<template>
  <div v-show="activePage === 'docs'" class="page-container fade-in">
    <div class="section-header">
      <div>
        <h2 class="section-title">使用指南</h2>
        <p class="form-hint">快速上手 Proxy Pool 代理池管理系统</p>
      </div>
      <div class="btn-group">
        <a href="/docs" target="_blank" class="btn btn-secondary">
          API 文档
        </a>
      </div>
    </div>

    <!-- Quick Start -->
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">快速开始</h3>
        <p class="text-muted text-sm" style="margin-bottom: 16px;">按照以下 5 个步骤快速配置代理池：</p>
        <div class="quick-start-steps">
          <div class="quick-start-step">
            <div class="step-number">1</div>
            <div class="step-content">
              <h4 class="step-title">添加订阅源</h4>
              <p class="step-desc">导航到「订阅管理」页面，添加你的代理订阅 URL，系统将自动获取最新节点。</p>
            </div>
          </div>
          <div class="quick-start-step">
            <div class="step-number">2</div>
            <div class="step-content">
              <h4 class="step-title">创建代理池</h4>
              <p class="step-desc">导航到「代理池」页面，创建落地代理池，设置筛选条件来过滤节点。</p>
            </div>
          </div>
          <div class="quick-start-step">
            <div class="step-number">3</div>
            <div class="step-content">
              <h4 class="step-title">配置入站端口</h4>
              <p class="step-desc">导航到「入站端口」页面，创建一个入站端口，绑定到你的代理池，客户端将通过此端口连接。</p>
            </div>
          </div>
          <div class="quick-start-step">
            <div class="step-number">4</div>
            <div class="step-content">
              <h4 class="step-title">测试代理</h4>
              <p class="step-desc">导航到「任务中心」页面，运行测速任务，测试所有节点的连通性和延迟。</p>
            </div>
          </div>
          <div class="quick-start-step">
            <div class="step-number">5</div>
            <div class="step-content">
              <h4 class="step-title">开始使用</h4>
              <p class="step-desc">使用入站端口地址配置你的客户端，即可开始使用代理服务。</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Feature Overview -->
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">功能概览</h3>
        <div class="feature-grid">
          <div class="feature-item">
            <div class="feature-icon">🔗</div>
            <div class="feature-info">
              <h4 class="feature-name">代理节点</h4>
              <p class="feature-desc">查看和管理所有代理节点，支持筛选和批量操作</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">⛓️</div>
            <div class="feature-info">
              <h4 class="feature-name">代理池</h4>
              <p class="feature-desc">创建和配置代理池，支持前置池和落地池</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">📡</div>
            <div class="feature-info">
              <h4 class="feature-name">订阅管理</h4>
              <p class="feature-desc">管理代理订阅源，自动获取最新节点</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">⚙️</div>
            <div class="feature-info">
              <h4 class="feature-name">任务中心</h4>
              <p class="feature-desc">批量测速、检测解锁、导入导出</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🔌</div>
            <div class="feature-info">
              <h4 class="feature-name">入站端口</h4>
              <p class="feature-desc">配置客户端连接的入口端口</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🔧</div>
            <div class="feature-info">
              <h4 class="feature-name">设置</h4>
              <p class="feature-desc">自定义界面偏好和行为</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- FAQ -->
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">常见问题</h3>
        <div class="faq-list">
          <div v-for="(faq, idx) in faqs" :key="'faq-' + idx" class="faq-item">
            <div class="faq-question" @click="toggleFaq(idx)">
              <span class="faq-icon" :class="{ expanded: expandedFaqs[idx] }">▶</span>
              <span>{{ faq.question }}</span>
            </div>
            <div v-if="expandedFaqs[idx]" class="faq-answer">
              {{ faq.answer }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- API Reference -->
    <div class="card">
      <div class="card-body">
        <h3 class="settings-title">API 参考</h3>
        <p class="text-muted text-sm" style="margin-bottom: 16px;">
          Proxy Pool 提供完整的 REST API，可用于自动化管理和集成。
        </p>
        <div class="api-reference">
          <div class="api-info">
            <h4 class="api-title">FastAPI 自动生成文档</h4>
            <p class="text-muted text-sm">访问以下地址查看完整的 API 文档：</p>
            <code class="api-url">/api/docs</code>
          </div>
          <a href="/api/docs" target="_blank" class="btn btn-primary">
            打开 API 文档
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "DocsPage",
  data() {
    return {
      expandedFaqs: {},
      faqs: [
        {
          question: '如何添加代理？',
          answer: '在「订阅管理」页面添加你的代理订阅 URL，系统将自动获取最新节点列表并同步到数据库。'
        },
        {
          question: '前置池和落地池有什么区别？',
          answer: '前置池是代理链的入口，负责接收客户端请求；落地池是代理链的出口，负责最终转发到目标网站。两者组合可以实现多跳代理。'
        },
        {
          question: '如何提高代理速度？',
          answer: '在代理池配置中使用低延迟筛选条件，选择延迟最低的节点。同时定期运行测速任务，保持节点池的健康状态。'
        },
        {
          question: '如何备份配置？',
          answer: '使用设置页面的配置导出功能，可以将所有代理池、订阅源和端口配置导出为文件，便于迁移或恢复。'
        }
      ],
    };
  },
  methods: {
    toggleFaq(idx) {
      this.expandedFaqs = {
        ...this.expandedFaqs,
        [idx]: !this.expandedFaqs[idx],
      };
    },
  },
};
</script>

<style scoped>
/* Quick Start Steps */
.quick-start-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.quick-start-step {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px;
}

.step-desc {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}

/* Feature Grid */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.feature-item {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.feature-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.feature-info {
  flex: 1;
}

.feature-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px;
}

.feature-desc {
  font-size: 12px;
  color: var(--muted);
  margin: 0;
  line-height: 1.4;
}

/* FAQ */
.faq-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.faq-item {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.faq-question {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--panel-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
  transition: background var(--transition);
}

.faq-question:hover {
  background: var(--line-soft);
}

.faq-icon {
  font-size: 10px;
  transition: transform var(--transition);
}

.faq-icon.expanded {
  transform: rotate(90deg);
}

.faq-answer {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}

/* Troubleshooting */
.troubleshoot-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.troubleshoot-item {
  padding: 16px;
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
}

.troubleshoot-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.troubleshoot-icon {
  font-size: 16px;
}

.troubleshoot-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--warning-text);
}

.troubleshoot-solution {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.5;
}

/* API Reference */
.api-reference {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.api-info {
  flex: 1;
}

.api-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px;
}

.api-url {
  display: inline-block;
  padding: 4px 8px;
  background: var(--line-soft);
  border-radius: var(--radius-sm);
  font-family: monospace;
  font-size: 13px;
  color: var(--accent);
  margin-top: 8px;
}

/* Responsive */
@media (max-width: 768px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }

  .api-reference {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }
}
</style>
