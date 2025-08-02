/**
 * 日志管理组件
 * 提供系统日志和任务日志的查看和管理功能
 */

class LogsManager {
    constructor() {
        this.currentView = 'system'; // 'system' | 'tasks' | 'errors'
        this.logs = [];
        this.filters = {
            level: 'all', // 'all' | 'info' | 'warning' | 'error' | 'debug'
            search: '',
            dateRange: {
                start: null,
                end: null
            },
            taskId: null
        };
        this.pagination = {
            page: 1,
            size: 50,
            total: 0
        };
        this.autoRefresh = false;
        this.refreshInterval = null;
        this.isLoading = false;
    }

    /**
     * 初始化日志管理器
     */
    async init() {
        console.log('初始化日志管理器...');
        this.setupEventListeners();
        await this.loadLogs();
        this.startAutoRefresh();
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 视图切换
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-log-view]')) {
                const view = e.target.dataset.logView;
                this.switchView(view);
            }
        });

        // 过滤器变化
        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-log-filter]')) {
                const filterType = e.target.dataset.logFilter;
                const value = e.target.value;
                this.updateFilter(filterType, value);
            }
        });

        // 搜索
        document.addEventListener('input', (e) => {
            if (e.target.matches('[data-log-search]')) {
                this.debounceSearch(e.target.value);
            }
        });

        // 分页
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-log-page]')) {
                const page = parseInt(e.target.dataset.logPage);
                this.changePage(page);
            }
        });

        // 自动刷新切换
        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-auto-refresh]')) {
                this.toggleAutoRefresh(e.target.checked);
            }
        });

        // 清理日志
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-clear-logs]')) {
                this.clearLogs();
            }
        });

        // 导出日志
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-export-logs]')) {
                this.exportLogs();
            }
        });

        // 刷新日志
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-refresh-logs]')) {
                this.loadLogs();
            }
        });
    }

    /**
     * 切换视图
     * @param {string} view - 视图类型
     */
    async switchView(view) {
        if (this.currentView === view) return;
        
        this.currentView = view;
        this.pagination.page = 1;
        
        // 更新导航状态
        this.updateNavigation();
        
        // 重新加载日志
        await this.loadLogs();
    }

    /**
     * 更新导航状态
     */
    updateNavigation() {
        const navItems = document.querySelectorAll('[data-log-view]');
        navItems.forEach(item => {
            const isActive = item.dataset.logView === this.currentView;
            item.classList.toggle('active', isActive);
            item.classList.toggle('bg-blue-100', isActive);
            item.classList.toggle('text-blue-600', isActive);
        });
    }

    /**
     * 更新过滤器
     * @param {string} filterType - 过滤器类型
     * @param {*} value - 过滤器值
     */
    async updateFilter(filterType, value) {
        if (filterType === 'dateStart' || filterType === 'dateEnd') {
            const dateType = filterType === 'dateStart' ? 'start' : 'end';
            this.filters.dateRange[dateType] = value || null;
        } else {
            this.filters[filterType] = value;
        }
        
        this.pagination.page = 1;
        await this.loadLogs();
    }

    /**
     * 防抖搜索
     * @param {string} query - 搜索查询
     */
    debounceSearch(query) {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.updateFilter('search', query);
        }, 300);
    }

    /**
     * 切换页面
     * @param {number} page - 页码
     */
    async changePage(page) {
        if (page < 1 || page > Math.ceil(this.pagination.total / this.pagination.size)) {
            return;
        }
        
        this.pagination.page = page;
        await this.loadLogs();
    }

    /**
     * 切换自动刷新
     * @param {boolean} enabled - 是否启用
     */
    toggleAutoRefresh(enabled) {
        this.autoRefresh = enabled;
        
        if (enabled) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }

    /**
     * 开始自动刷新
     */
    startAutoRefresh() {
        if (!this.autoRefresh) return;
        
        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => {
            if (!this.isLoading) {
                this.loadLogs(true); // 静默刷新
            }
        }, 10000); // 每10秒刷新一次
    }

    /**
     * 停止自动刷新
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * 加载日志
     * @param {boolean} silent - 是否静默加载
     */
    async loadLogs(silent = false) {
        if (this.isLoading && !silent) return;
        
        this.isLoading = true;
        
        if (!silent) {
            this.showLoading();
        }
        
        try {
            let endpoint;
            const params = {
                page: this.pagination.page,
                size: this.pagination.size,
                level: this.filters.level !== 'all' ? this.filters.level : undefined,
                search: this.filters.search || undefined,
                start_date: this.filters.dateRange.start || undefined,
                end_date: this.filters.dateRange.end || undefined
            };
            
            // 根据当前视图选择不同的API端点
            switch (this.currentView) {
                case 'system':
                    endpoint = '/api/logs/system';
                    break;
                case 'tasks':
                    endpoint = '/api/logs/tasks';
                    if (this.filters.taskId) {
                        params.task_id = this.filters.taskId;
                    }
                    break;
                case 'errors':
                    endpoint = '/api/logs/errors';
                    break;
                default:
                    endpoint = '/api/logs/system';
            }
            
            const result = await api.get(endpoint, params);
            
            if (result.success) {
                this.logs = result.data.logs || [];
                this.pagination.total = result.data.total || 0;
                this.render();
            } else {
                throw new Error(result.error || '加载日志失败');
            }
        } catch (error) {
            console.error('加载日志失败:', error);
            app.showError('加载日志失败: ' + error.message);
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }

    /**
     * 清理日志
     */
    async clearLogs() {
        if (!confirm('确定要清理所有日志吗？此操作不可撤销。')) {
            return;
        }
        
        try {
            const result = await api.post('/api/logs/clear', {
                type: this.currentView
            });
            
            if (result.success) {
                app.showSuccess('日志清理成功');
                await this.loadLogs();
            } else {
                throw new Error(result.error || '清理日志失败');
            }
        } catch (error) {
            console.error('清理日志失败:', error);
            app.showError('清理日志失败: ' + error.message);
        }
    }

    /**
     * 导出日志
     */
    async exportLogs() {
        try {
            const params = {
                type: this.currentView,
                level: this.filters.level !== 'all' ? this.filters.level : undefined,
                search: this.filters.search || undefined,
                start_date: this.filters.dateRange.start || undefined,
                end_date: this.filters.dateRange.end || undefined
            };
            
            const queryString = new URLSearchParams(params).toString();
            const url = `/api/logs/export?${queryString}`;
            
            // 创建下载链接
            const link = document.createElement('a');
            link.href = url;
            link.download = `logs_${this.currentView}_${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            app.showSuccess('日志导出成功');
        } catch (error) {
            console.error('导出日志失败:', error);
            app.showError('导出日志失败: ' + error.message);
        }
    }

    /**
     * 显示加载状态
     */
    showLoading() {
        const container = document.querySelector('#logs-container');
        if (container) {
            container.classList.add('opacity-50');
        }
    }

    /**
     * 隐藏加载状态
     */
    hideLoading() {
        const container = document.querySelector('#logs-container');
        if (container) {
            container.classList.remove('opacity-50');
        }
    }

    /**
     * 渲染日志列表
     */
    render() {
        const container = document.querySelector('#logs-container');
        if (!container) return;
        
        container.innerHTML = this.getLogsHTML();
        
        // 更新分页
        this.renderPagination();
        
        // 更新统计信息
        this.updateStats();
    }

    /**
     * 获取日志HTML
     * @returns {string} HTML字符串
     */
    getLogsHTML() {
        if (this.logs.length === 0) {
            return `
                <div class="text-center py-12">
                    <i data-lucide="file-text" class="mx-auto h-12 w-12 text-gray-400"></i>
                    <h3 class="mt-2 text-sm font-medium text-gray-900">暂无日志</h3>
                    <p class="mt-1 text-sm text-gray-500">当前筛选条件下没有找到日志记录</p>
                </div>
            `;
        }
        
        return `
            <div class="space-y-2">
                ${this.logs.map(log => this.getLogItemHTML(log)).join('')}
            </div>
        `;
    }

    /**
     * 获取单个日志项HTML
     * @param {Object} log - 日志对象
     * @returns {string} HTML字符串
     */
    getLogItemHTML(log) {
        const levelColors = {
            'DEBUG': 'text-gray-600 bg-gray-100',
            'INFO': 'text-blue-600 bg-blue-100',
            'WARNING': 'text-yellow-600 bg-yellow-100',
            'ERROR': 'text-red-600 bg-red-100',
            'CRITICAL': 'text-red-800 bg-red-200'
        };
        
        const levelColor = levelColors[log.level] || 'text-gray-600 bg-gray-100';
        const timestamp = new Date(log.timestamp).toLocaleString('zh-CN');
        
        return `
            <div class="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
                <div class="flex items-start justify-between">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${levelColor}">
                                ${log.level}
                            </span>
                            <span class="text-sm text-gray-500">${timestamp}</span>
                            ${log.task_id ? `<span class="text-xs text-gray-400">任务 #${log.task_id}</span>` : ''}
                            ${log.module ? `<span class="text-xs text-gray-400">[${log.module}]</span>` : ''}
                        </div>
                        <p class="text-sm text-gray-900 whitespace-pre-wrap">${this.escapeHtml(log.message)}</p>
                        ${log.details ? `
                            <details class="mt-2">
                                <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-700">详细信息</summary>
                                <pre class="mt-1 text-xs text-gray-600 bg-gray-50 p-2 rounded overflow-x-auto">${this.escapeHtml(log.details)}</pre>
                            </details>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 渲染分页
     */
    renderPagination() {
        const paginationContainer = document.querySelector('#logs-pagination');
        if (!paginationContainer) return;
        
        const totalPages = Math.ceil(this.pagination.total / this.pagination.size);
        const currentPage = this.pagination.page;
        
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }
        
        let paginationHTML = `
            <div class="flex items-center justify-between">
                <div class="text-sm text-gray-700">
                    显示第 ${(currentPage - 1) * this.pagination.size + 1} - ${Math.min(currentPage * this.pagination.size, this.pagination.total)} 条，共 ${this.pagination.total} 条
                </div>
                <div class="flex space-x-1">
        `;
        
        // 上一页按钮
        paginationHTML += `
            <button data-log-page="${currentPage - 1}" 
                    class="px-3 py-1 text-sm border rounded ${currentPage === 1 ? 'text-gray-400 cursor-not-allowed' : 'text-gray-700 hover:bg-gray-50'}" 
                    ${currentPage === 1 ? 'disabled' : ''}>
                上一页
            </button>
        `;
        
        // 页码按钮
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <button data-log-page="${i}" 
                        class="px-3 py-1 text-sm border rounded ${i === currentPage ? 'bg-blue-500 text-white' : 'text-gray-700 hover:bg-gray-50'}">
                    ${i}
                </button>
            `;
        }
        
        // 下一页按钮
        paginationHTML += `
            <button data-log-page="${currentPage + 1}" 
                    class="px-3 py-1 text-sm border rounded ${currentPage === totalPages ? 'text-gray-400 cursor-not-allowed' : 'text-gray-700 hover:bg-gray-50'}" 
                    ${currentPage === totalPages ? 'disabled' : ''}>
                下一页
            </button>
        `;
        
        paginationHTML += `
                </div>
            </div>
        `;
        
        paginationContainer.innerHTML = paginationHTML;
    }

    /**
     * 更新统计信息
     */
    updateStats() {
        const statsContainer = document.querySelector('#logs-stats');
        if (!statsContainer) return;
        
        const stats = this.calculateStats();
        
        statsContainer.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-white p-4 rounded-lg border">
                    <div class="text-2xl font-bold text-blue-600">${stats.total}</div>
                    <div class="text-sm text-gray-500">总计</div>
                </div>
                <div class="bg-white p-4 rounded-lg border">
                    <div class="text-2xl font-bold text-red-600">${stats.errors}</div>
                    <div class="text-sm text-gray-500">错误</div>
                </div>
                <div class="bg-white p-4 rounded-lg border">
                    <div class="text-2xl font-bold text-yellow-600">${stats.warnings}</div>
                    <div class="text-sm text-gray-500">警告</div>
                </div>
                <div class="bg-white p-4 rounded-lg border">
                    <div class="text-2xl font-bold text-green-600">${stats.info}</div>
                    <div class="text-sm text-gray-500">信息</div>
                </div>
            </div>
        `;
    }

    /**
     * 计算统计信息
     * @returns {Object} 统计数据
     */
    calculateStats() {
        const stats = {
            total: this.pagination.total,
            errors: 0,
            warnings: 0,
            info: 0
        };
        
        this.logs.forEach(log => {
            switch (log.level) {
                case 'ERROR':
                case 'CRITICAL':
                    stats.errors++;
                    break;
                case 'WARNING':
                    stats.warnings++;
                    break;
                case 'INFO':
                    stats.info++;
                    break;
            }
        });
        
        return stats;
    }

    /**
     * 转义HTML
     * @param {string} text - 要转义的文本
     * @returns {string} 转义后的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 清理资源
     */
    cleanup() {
        this.stopAutoRefresh();
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
    }
}

// 导出日志管理器
window.LogsManager = LogsManager;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LogsManager;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return LogsManager;
    });
}