/**
 * 数据分析组件
 * 提供数据可视化和分析功能
 */

class AnalyticsManager {
    constructor() {
        this.charts = new Map();
        this.currentTimeRange = '7d';
        this.currentProject = null;
        this.refreshInterval = null;
        this.autoRefresh = false;
    }

    /**
     * 初始化分析管理器
     */
    async init() {
        console.log('初始化数据分析管理器...');
        this.setupEventListeners();
        await this.loadAnalyticsData();
        this.startAutoRefresh();
    }

    async render() {
        console.log('渲染数据分析管理器...');
        await this.loadAnalyticsData();
    }

    /**
     * 加载分析数据
     */
    async loadAnalyticsData() {
        this.showLoading(true);
        
        try {
            // 并行加载多个数据源
            const [overviewResult, trendsResult, performanceResult] = await Promise.all([
                this.loadOverviewData(),
                this.loadTrendsData(),
                this.loadPerformanceData()
            ]);
            
            if (overviewResult.success) {
                this.renderOverviewStats(overviewResult.data);
            }
            
            if (trendsResult.success) {
                this.renderTrendsChart(trendsResult.data);
            }
            
            if (performanceResult.success) {
                this.renderPerformanceCharts(performanceResult.data);
            }
            
        } catch (error) {
            console.error('加载分析数据失败:', error);
            this.showError('加载分析数据失败，请检查网络连接');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * 加载概览数据
     */
    async loadOverviewData() {
        try {
            const params = {
                time_range: this.currentTimeRange
            };
            
            if (this.currentProject) {
                params.project_id = this.currentProject;
            }
            
            return await api.getAnalyticsOverview(params);
        } catch (error) {
            console.error('加载概览数据失败:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * 加载趋势数据
     */
    async loadTrendsData() {
        try {
            const params = {
                time_range: this.currentTimeRange,
                granularity: this.getGranularity()
            };
            
            if (this.currentProject) {
                params.project_id = this.currentProject;
            }
            
            return await api.getAnalyticsTrends(params);
        } catch (error) {
            console.error('加载趋势数据失败:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * 加载性能数据
     */
    async loadPerformanceData() {
        try {
            const params = {
                time_range: this.currentTimeRange
            };
            
            if (this.currentProject) {
                params.project_id = this.currentProject;
            }
            
            return await api.getAnalyticsPerformance(params);
        } catch (error) {
            console.error('加载性能数据失败:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * 获取时间粒度
     */
    getGranularity() {
        const granularityMap = {
            '1d': 'hour',
            '7d': 'day',
            '30d': 'day',
            '90d': 'week',
            '1y': 'month'
        };
        
        return granularityMap[this.currentTimeRange] || 'day';
    }

    /**
     * 渲染概览统计
     * @param {Object} data - 概览数据
     */
    renderOverviewStats(data) {
        const container = document.getElementById('analytics-overview');
        if (!container) return;
        
        const stats = [
            {
                title: '总任务数',
                value: data.total_tasks || 0,
                change: data.tasks_change || 0,
                icon: 'clipboard-list',
                color: 'blue'
            },
            {
                title: '成功率',
                value: `${data.success_rate || 0}%`,
                change: data.success_rate_change || 0,
                icon: 'check-circle',
                color: 'green'
            },
            {
                title: '平均执行时间',
                value: helpers.formatDuration(data.avg_execution_time || 0),
                change: data.execution_time_change || 0,
                icon: 'clock',
                color: 'yellow'
            },
            {
                title: '错误率',
                value: `${data.error_rate || 0}%`,
                change: data.error_rate_change || 0,
                icon: 'alert-circle',
                color: 'red'
            }
        ];
        
        const statsHtml = stats.map(stat => `
            <div class="stat-card stat-card-${stat.color}">
                <div class="stat-icon">
                    <i data-lucide="${stat.icon}" class="w-6 h-6"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stat.value}</div>
                    <div class="stat-title">${stat.title}</div>
                    <div class="stat-change ${stat.change >= 0 ? 'positive' : 'negative'}">
                        <i data-lucide="${stat.change >= 0 ? 'trending-up' : 'trending-down'}" class="w-3 h-3 mr-1"></i>
                        ${Math.abs(stat.change)}%
                    </div>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = `
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                ${statsHtml}
            </div>
        `;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 渲染趋势图表
     * @param {Object} data - 趋势数据
     */
    renderTrendsChart(data) {
        const canvas = document.getElementById('trends-chart');
        if (!canvas || !window.Chart) return;
        
        // 销毁现有图表
        if (this.charts.has('trends')) {
            this.charts.get('trends').destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: '成功任务',
                        data: data.successful_tasks || [],
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '失败任务',
                        data: data.failed_tasks || [],
                        borderColor: '#EF4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '总任务',
                        data: data.total_tasks || [],
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: false,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#374151',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        });
        
        this.charts.set('trends', chart);
    }

    /**
     * 渲染性能图表
     * @param {Object} data - 性能数据
     */
    renderPerformanceCharts(data) {
        this.renderExecutionTimeChart(data.execution_times || []);
        this.renderStatusDistributionChart(data.status_distribution || {});
        this.renderProjectPerformanceChart(data.project_performance || []);
    }

    /**
     * 渲染执行时间图表
     * @param {Array} data - 执行时间数据
     */
    renderExecutionTimeChart(data) {
        const canvas = document.getElementById('execution-time-chart');
        if (!canvas || !window.Chart) return;
        
        // 销毁现有图表
        if (this.charts.has('execution-time')) {
            this.charts.get('execution-time').destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.time_range),
                datasets: [{
                    label: '平均执行时间 (秒)',
                    data: data.map(item => item.avg_time),
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderColor: '#3B82F6',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        });
        
        this.charts.set('execution-time', chart);
    }

    /**
     * 渲染状态分布图表
     * @param {Object} data - 状态分布数据
     */
    renderStatusDistributionChart(data) {
        const canvas = document.getElementById('status-distribution-chart');
        if (!canvas || !window.Chart) return;
        
        // 销毁现有图表
        if (this.charts.has('status-distribution')) {
            this.charts.get('status-distribution').destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['已完成', '运行中', '待执行', '失败', '已取消'],
                datasets: [{
                    data: [
                        data.completed || 0,
                        data.running || 0,
                        data.pending || 0,
                        data.failed || 0,
                        data.cancelled || 0
                    ],
                    backgroundColor: [
                        '#10B981',
                        '#3B82F6',
                        '#F59E0B',
                        '#EF4444',
                        '#6B7280'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        this.charts.set('status-distribution', chart);
    }

    /**
     * 渲染项目性能图表
     * @param {Array} data - 项目性能数据
     */
    renderProjectPerformanceChart(data) {
        const canvas = document.getElementById('project-performance-chart');
        if (!canvas || !window.Chart) return;
        
        // 销毁现有图表
        if (this.charts.has('project-performance')) {
            this.charts.get('project-performance').destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        const chart = new Chart(ctx, {
            type: 'horizontalBar',
            data: {
                labels: data.map(item => item.project_name),
                datasets: [
                    {
                        label: '成功率 (%)',
                        data: data.map(item => item.success_rate),
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderColor: '#10B981',
                        borderWidth: 1
                    },
                    {
                        label: '任务数量',
                        data: data.map(item => item.task_count),
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderColor: '#3B82F6',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: false,
                        position: 'right'
                    }
                }
            }
        });
        
        this.charts.set('project-performance', chart);
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 时间范围选择器
        const timeRangeSelect = document.getElementById('time-range-select');
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', (e) => {
                this.currentTimeRange = e.target.value;
                this.loadAnalyticsData();
            });
        }

        // 项目过滤器
        const projectSelect = document.getElementById('analytics-project-select');
        if (projectSelect) {
            projectSelect.addEventListener('change', (e) => {
                this.currentProject = e.target.value || null;
                this.loadAnalyticsData();
            });
        }

        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-analytics');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadAnalyticsData();
            });
        }

        // 自动刷新开关
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.autoRefresh = e.target.checked;
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        // 导出按钮
        const exportBtn = document.getElementById('export-analytics');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportAnalyticsData();
            });
        }
    }

    /**
     * 开始自动刷新
     */
    startAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        if (this.autoRefresh) {
            this.refreshInterval = setInterval(() => {
                this.loadAnalyticsData();
            }, 30000); // 30秒刷新一次
        }
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
     * 导出分析数据
     */
    async exportAnalyticsData() {
        try {
            const params = {
                time_range: this.currentTimeRange,
                format: 'csv'
            };
            
            if (this.currentProject) {
                params.project_id = this.currentProject;
            }
            
            const result = await api.exportAnalytics(params);
            
            if (result.success) {
                // 创建下载链接
                const blob = new Blob([result.data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analytics_${this.currentTimeRange}_${Date.now()}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showSuccess('分析数据导出成功');
            } else {
                this.showError('导出失败: ' + result.error);
            }
        } catch (error) {
            console.error('导出分析数据失败:', error);
            this.showError('导出失败，请重试');
        }
    }

    /**
     * 销毁所有图表
     */
    destroyCharts() {
        this.charts.forEach(chart => {
            chart.destroy();
        });
        this.charts.clear();
    }

    /**
     * 清理资源
     */
    cleanup() {
        this.stopAutoRefresh();
        this.destroyCharts();
    }

    /**
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('analytics-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        console.error('数据分析错误:', message);
        // 这里可以集成到全局通知系统
        alert('错误: ' + message);
    }

    /**
     * 显示成功信息
     * @param {string} message - 成功信息
     */
    showSuccess(message) {
        console.log('数据分析成功:', message);
        // 这里可以集成到全局通知系统
        alert('成功: ' + message);
    }

    /**
     * 获取数据分析HTML模板
     * @returns {string} HTML模板
     */
    static getTemplate() {
        return `
            <div class="analytics-container">
                <!-- 工具栏 -->
                <div class="card mb-6">
                    <div class="card-body">
                        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
                            <div class="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
                                <select id="time-range-select" class="filter-select">
                                    <option value="1d">最近1天</option>
                                    <option value="7d" selected>最近7天</option>
                                    <option value="30d">最近30天</option>
                                    <option value="90d">最近90天</option>
                                    <option value="1y">最近1年</option>
                                </select>
                                
                                <select id="analytics-project-select" class="filter-select">
                                    <option value="">所有项目</option>
                                </select>
                            </div>
                            
                            <div class="flex items-center space-x-3">
                                <label class="flex items-center space-x-2">
                                    <input type="checkbox" id="auto-refresh-toggle" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                                    <span class="text-sm text-gray-700">自动刷新</span>
                                </label>
                                <button id="export-analytics" class="btn btn-outline">
                                    <i data-lucide="download" class="w-4 h-4 mr-2"></i>
                                    导出
                                </button>
                                <button id="refresh-analytics" class="btn btn-outline">
                                    <i data-lucide="refresh-cw" class="w-4 h-4 mr-2"></i>
                                    刷新
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 加载状态 -->
                <div id="analytics-loading" class="text-center py-8" style="display: none;">
                    <div class="loading-dots">
                        <span style="--i: 0"></span>
                        <span style="--i: 1"></span>
                        <span style="--i: 2"></span>
                    </div>
                    <div class="mt-2 text-gray-600">加载中...</div>
                </div>
                
                <!-- 概览统计 -->
                <div id="analytics-overview" class="mb-6"></div>
                
                <!-- 图表区域 -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- 趋势图表 -->
                    <div class="card lg:col-span-2">
                        <div class="card-header">
                            <h3 class="card-title">任务执行趋势</h3>
                        </div>
                        <div class="card-body">
                            <div class="chart-container" style="height: 300px;">
                                <canvas id="trends-chart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 执行时间图表 -->
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">执行时间分布</h3>
                        </div>
                        <div class="card-body">
                            <div class="chart-container" style="height: 250px;">
                                <canvas id="execution-time-chart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 状态分布图表 -->
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">任务状态分布</h3>
                        </div>
                        <div class="card-body">
                            <div class="chart-container" style="height: 250px;">
                                <canvas id="status-distribution-chart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 项目性能图表 -->
                    <div class="card lg:col-span-2">
                        <div class="card-header">
                            <h3 class="card-title">项目性能对比</h3>
                        </div>
                        <div class="card-body">
                            <div class="chart-container" style="height: 300px;">
                                <canvas id="project-performance-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// 创建全局实例
const analyticsManager = new AnalyticsManager();

// 导出到全局
window.analyticsManager = analyticsManager;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = analyticsManager;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return analyticsManager;
    });
}