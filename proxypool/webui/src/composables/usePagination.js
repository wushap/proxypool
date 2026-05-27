// src/composables/usePagination.js
// 分页逻辑 composable

import { ref, computed } from 'vue'

/**
 * 分页 composable
 * @param {number} initialPerPage - 初始每页条数
 * @returns {object} 分页相关状态和方法
 */
export function usePagination(initialPerPage = 10) {
  const page = ref(1)
  const perPage = ref(initialPerPage)
  const totalItems = ref(0)

  const totalPages = computed(() => {
    return Math.max(1, Math.ceil(totalItems.value / perPage.value))
  })

  const canPrev = computed(() => page.value > 1)
  const canNext = computed(() => page.value < totalPages.value)

  const pageIndicator = computed(() => {
    return `${page.value}/${totalPages.value} (${totalItems.value})`
  })

  function goToPrev() {
    if (canPrev.value) page.value--
  }

  function goToNext() {
    if (canNext.value) page.value++
  }

  function goToPage(p) {
    page.value = Math.max(1, Math.min(p, totalPages.value))
  }

  function reset() {
    page.value = 1
  }

  function setTotal(total) {
    totalItems.value = total
    // 防止当前页超出范围
    if (page.value > totalPages.value) {
      page.value = totalPages.value
    }
  }

  function paginate(items) {
    setTotal(items.length)
    const start = (page.value - 1) * perPage.value
    return items.slice(start, start + perPage.value)
  }

  return {
    page,
    perPage,
    totalItems,
    totalPages,
    canPrev,
    canNext,
    pageIndicator,
    goToPrev,
    goToNext,
    goToPage,
    reset,
    setTotal,
    paginate,
  }
}
