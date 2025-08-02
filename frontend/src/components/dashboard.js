/**
 * 仪表板组件
 * 提供系统概览和统计信息展示
 */

class Dashboard {
    constructor() {
        this.charts = {};
        this.refreshInterval = null;
        this.autoRefreshEnabled = true;
        this.refreshIntervalMs = 30000; // 30秒自动刷新
    }

    /**
     * 初始化仪表板
     */
    async init() {
        console.log('初始化仪表板...');
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    async render() {
        console.log('渲染仪表板...');
        await this.loadDashboardData();
    }

    /**
     * 加载仪表板数据
     */
    async loadDashboardData() {
        this.showLoading(true);
        
        try {
            // 并行加载所有数据，添加错误处理确保单个API失败不影响其他数据
            const [statsResult, healthResult, activityResult, quickStatsResult, taskStatsResult, projectStatsResult] = await Promise.all([
                api.getDashboardStats().catch(err => ({ success: false, data: this.getDefaultStats(), error: err })),
                api.getSystemHealth().catch(err => ({ success: false, data: this.getDefaultHealth(), error: err })),
                api.getRecentActivity(10).catch(err => ({ success: false, data: { activities: [] }, error: err })),
                api.getQuickStats().catch(err => ({ success: false, data: this.getDefaultQuickStats(), error: err })),
                api.get('/api/tasks/stats').catch(err => ({ success: false, data: { stats: {} }, error: err })),
                api.get('/api/projects/stats').catch(err => ({ success: false, data: { stats: {} }, error: err }))
            ]);

            // 处理统计数据 - 合并多个API的数据
            let combinedStats = this.getDefaultStats();
            if (statsResult.success && statsResult.data) {
                combinedStats = { ...combinedStats, ...statsResult.data };
            }
            if (taskStatsResult.success && taskStatsResult.data && taskStatsResult.data.stats) {
                const taskStats = taskStatsResult.data.stats;
                combinedStats.total_tasks = taskStats.total || 0;
                combinedStats.completed_tasks = taskStats.success || 0;
                combinedStats.running_tasks = taskStats.in_progress || 0;
                combinedStats.task_status_distribution = {
                    pending: taskStats.pending || 0,
                    running: taskStats.in_progress || 0,
                    completed: taskStats.success || 0,
                    failed: taskStats.failed || 0,
                    cancelled: taskStats.retry || 0
                };
            }
            if (projectStatsResult.success && projectStatsResult.data && projectStatsResult.data.stats) {
                const projectStats = projectStatsResult.data.stats;
                combinedStats.total_projects = projectStats.total_projects || 0;
                combinedStats.project_progress = (projectStats.project_breakdown || []).map(project => ({
                    name: project.name,
                    progress: project.success_rate || 0
                }));
            }
            this.renderStats(combinedStats);

            // 处理系统健康状态
            let healthData = this.getDefaultHealth();
            if (healthResult.success && healthResult.data) {
                const health = healthResult.data;
                healthData = {
                    api_status: health.status === 'healthy' ? 'healthy' : 'warning',
                    database_status: health.database_status || 'warning',
                    task_scheduler_status: health.task_status || 'warning',
                    cpu_usage: health.cpu_usage || 0,
                    memory_usage: health.memory_usage || 0,
                    disk_usage: health.disk_usage || 0,
                    last_check: health.last_check || new Date().toISOString()
                };
            }
            this.renderSystemHealth(healthData);

            // 处理最近活动
            if (activityResult.success && activityResult.data) {
                this.renderRecentActivity(activityResult.data);
            } else {
                console.error('获取最近活动失败:', activityResult.error);
                this.renderRecentActivity({ activities: [] });
            }

            // 处理快速统计
            let quickStats = this.getDefaultQuickStats();
            if (quickStatsResult.success && quickStatsResult.data && quickStatsResult.data.stats) {
                const stats = quickStatsResult.data.stats;
                quickStats = {
                    today_tasks: stats.today_published || 0,
                    success_rate: projectStatsResult.success && projectStatsResult.data ? 
                        (projectStatsResult.data.stats.overall_success_rate || 0) : 0,
                    avg_execution_time: 0, // 暂时没有这个数据
                    active_projects: combinedStats.total_projects || 0
                };
            }
            this.renderQuickStats(quickStats);

            // 检查是否有API错误，显示警告但不阻止界面显示
            const errors = [statsResult, healthResult, activityResult, quickStatsResult]
                .filter(result => !result.success)
                .map(result => result.error?.message || '未知错误');
            
            if (errors.length > 0) {
                console.warn('部分数据加载失败:', errors);
                this.showWarning(`部分数据加载失败，显示模拟数据`);
            }

        } catch (error) {
            console.error('加载仪表板数据失败:', error);
            // 使用默认数据确保界面可以显示
            this.renderStats(this.getDefaultStats());
            this.renderSystemHealth(this.getDefaultHealth());
            this.renderRecentActivity({ activities: [] });
            this.renderQuickStats(this.getDefaultQuickStats());
            this.showError('加载数据失败，显示模拟数据');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * 渲染统计数据
     * @param {Object} stats - 统计数据
     */
    renderStats(stats) {
        const container = document.getElementById('dashboard-stats');
        if (!container) return;

        const statsHtml = `
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
                <div class="stat-card bg-blue-50">
                    <div class="stat-card-icon bg-blue-100">
                        <i data-lucide="activity" class="w-6 h-6 text-blue-600"></i>
                    </div>
                    <div class="stat-card-value text-blue-600">${helpers.formatNumber(stats.total_tasks || 0)}</div>
                    <div class="stat-card-label">总任务数</div>
                    <div class="stat-card-change ${stats.tasks_change >= 0 ? 'positive' : 'negative'}">
                        ${stats.tasks_change >= 0 ? '+' : ''}${helpers.formatNumber(stats.tasks_change || 0)}
                    </div>
                </div>
                
                <div class="stat-card bg-green-50">
                    <div class="stat-card-icon bg-green-100">
                        <i data-lucide="check-circle" class="w-6 h-6 text-green-600"></i>
                    </div>
                    <div class="stat-card-value text-green-600">${helpers.formatNumber(stats.completed_tasks || 0)}</div>
                    <div class="stat-card-label">已完成任务</div>
                    <div class="stat-card-change ${stats.completed_change >= 0 ? 'positive' : 'negative'}">
                        ${stats.completed_change >= 0 ? '+' : ''}${helpers.formatNumber(stats.completed_change || 0)}
                    </div>
                </div>
                
                <div class="stat-card bg-yellow-50">
                    <div class="stat-card-icon bg-yellow-100">
                        <i data-lucide="clock" class="w-6 h-6 text-yellow-600"></i>
                    </div>
                    <div class="stat-card-value text-yellow-600">${helpers.formatNumber(stats.running_tasks || 0)}</div>
                    <div class="stat-card-label">运行中任务</div>
                    <div class="stat-card-change ${stats.running_change >= 0 ? 'positive' : 'negative'}">
                        ${stats.running_change >= 0 ? '+' : ''}${helpers.formatNumber(stats.running_change || 0)}
                    </div>
                </div>
                
                <div class="stat-card bg-purple-50">
                    <div class="stat-card-icon bg-purple-100">
                        <i data-lucide="folder" class="w-6 h-6 text-purple-600"></i>
                    </div>
                    <div class="stat-card-value text-purple-600">${helpers.formatNumber(stats.total_projects || 0)}</div>
                    <div class="stat-card-label">项目数量</div>
                    <div class="stat-card-change ${stats.projects_change >= 0 ? 'positive' : 'negative'}">
                        ${stats.projects_change >= 0 ? '+' : ''}${helpers.formatNumber(stats.projects_change || 0)}
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = statsHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }

        // 渲染图表
        this.renderCharts(stats);
    }

    /**
     * 渲染图表
     * @param {Object} stats - 统计数据
     */
    renderCharts(stats) {
        // 任务状态分布图
        this.renderTaskStatusChart(stats.task_status_distribution || {});
        
        // 活动趋势图
        this.renderActivityTrendChart(stats.hourly_activity || []);
        
        // 项目进度图
        this.renderProjectProgressChart(stats.project_progress || []);
    }

    /**
     * 渲染任务状态分布图
     * @param {Object} distribution - 状态分布数据
     */
    renderTaskStatusChart(distribution) {
        const canvas = document.getElementById('task-status-chart');
        if (!canvas) return;

        // 销毁现有图表
        if (this.charts.taskStatus) {
            this.charts.taskStatus.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = {
            labels: ['待执行', '运行中', '已完成', '失败', '已取消'],
            datasets: [{
                data: [
                    distribution.pending || 0,
                    distribution.running || 0,
                    distribution.completed || 0,
                    distribution.failed || 0,
                    distribution.cancelled || 0
                ],
                backgroundColor: [
                    '#f59e0b',
                    '#3b82f6',
                    '#10b981',
                    '#ef4444',
                    '#6b7280'
                ],
                borderWidth: 0
            }]
        };

        this.charts.taskStatus = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * 渲染活动趋势图
     * @param {Array} hourlyData - 小时活动数据
     */
    renderActivityTrendChart(hourlyData) {
        const canvas = document.getElementById('activity-trend-chart');
        if (!canvas) return;

        // 销毁现有图表
        if (this.charts.activityTrend) {
            this.charts.activityTrend.destroy();
        }

        const ctx = canvas.getContext('2d');
        const labels = hourlyData.map(item => `${item.hour}:00`);
        const data = {
            labels: labels,
            datasets: [{
                label: '任务执行数',
                data: hourlyData.map(item => item.count),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        };

        this.charts.activityTrend = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    /**
     * 渲染项目进度图
     * @param {Array} projectData - 项目数据
     */
    renderProjectProgressChart(projectData) {
        const canvas = document.getElementById('project-progress-chart');
        if (!canvas) return;

        // 销毁现有图表
        if (this.charts.projectProgress) {
            this.charts.projectProgress.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = {
            labels: projectData.map(item => item.name),
            datasets: [{
                label: '完成率',
                data: projectData.map(item => item.progress),
                backgroundColor: 'rgba(16, 185, 129, 0.8)',
                borderColor: '#10b981',
                borderWidth: 1
            }]
        };

        this.charts.projectProgress = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    /**
     * 渲染系统健康状态
     * @param {Object} health - 健康状态数据
     */
    renderSystemHealth(health) {
        const container = document.getElementById('system-health');
        if (!container) return;

        const getStatusColor = (status) => {
            switch (status) {
                case 'healthy': return 'text-green-600 bg-green-100';
                case 'warning': return 'text-yellow-600 bg-yellow-100';
                case 'error': return 'text-red-600 bg-red-100';
                default: return 'text-gray-600 bg-gray-100';
            }
        };

        const getStatusIcon = (status) => {
            switch (status) {
                case 'healthy': return 'check-circle';
                case 'warning': return 'alert-triangle';
                case 'error': return 'x-circle';
                default: return 'help-circle';
            }
        };

        const healthHtml = `
            <div class="card">
                <div class="card-header">
                    <h3 class="text-lg font-semibold text-gray-900">系统健康状态</h3>
                    <span class="text-sm text-gray-500">最后检查: ${helpers.formatDate(health.last_check)}</span>
                </div>
                <div class="card-body">
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                <div class="w-8 h-8 rounded-full ${getStatusColor(health.api_status)} flex items-center justify-center">
                                    <i data-lucide="${getStatusIcon(health.api_status)}" class="w-4 h-4"></i>
                                </div>
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-900">API服务</div>
                                <div class="text-sm text-gray-500">${health.api_status === 'healthy' ? '正常' : health.api_status === 'warning' ? '警告' : '异常'}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                <div class="w-8 h-8 rounded-full ${getStatusColor(health.database_status)} flex items-center justify-center">
                                    <i data-lucide="${getStatusIcon(health.database_status)}" class="w-4 h-4"></i>
                                </div>
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-900">数据库</div>
                                <div class="text-sm text-gray-500">${health.database_status === 'healthy' ? '正常' : health.database_status === 'warning' ? '警告' : '异常'}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                <div class="w-8 h-8 rounded-full ${getStatusColor(health.task_scheduler_status)} flex items-center justify-center">
                                    <i data-lucide="${getStatusIcon(health.task_scheduler_status)}" class="w-4 h-4"></i>
                                </div>
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-900">任务调度器</div>
                                <div class="text-sm text-gray-500">${health.task_scheduler_status === 'healthy' ? '正常' : health.task_scheduler_status === 'warning' ? '警告' : '异常'}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div class="text-center">
                            <div class="text-2xl font-bold text-gray-900">${helpers.formatPercentage(health.cpu_usage, 100)}%</div>
                            <div class="text-sm text-gray-500">CPU使用率</div>
                            <div class="mt-2">
                                <div class="progress">
                                    <div class="progress-bar ${health.cpu_usage > 80 ? 'progress-bar-danger' : health.cpu_usage > 60 ? 'progress-bar-warning' : 'progress-bar-success'}" 
                                         style="width: ${health.cpu_usage}%"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="text-center">
                            <div class="text-2xl font-bold text-gray-900">${helpers.formatPercentage(health.memory_usage, 100)}%</div>
                            <div class="text-sm text-gray-500">内存使用率</div>
                            <div class="mt-2">
                                <div class="progress">
                                    <div class="progress-bar ${health.memory_usage > 80 ? 'progress-bar-danger' : health.memory_usage > 60 ? 'progress-bar-warning' : 'progress-bar-success'}" 
                                         style="width: ${health.memory_usage}%"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="text-center">
                            <div class="text-2xl font-bold text-gray-900">${helpers.formatPercentage(health.disk_usage, 100)}%</div>
                            <div class="text-sm text-gray-500">磁盘使用率</div>
                            <div class="mt-2">
                                <div class="progress">
                                    <div class="progress-bar ${health.disk_usage > 80 ? 'progress-bar-danger' : health.disk_usage > 60 ? 'progress-bar-warning' : 'progress-bar-success'}" 
                                         style="width: ${health.disk_usage}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = healthHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 渲染最近活动
     * @param {Object} activityData - 活动数据
     */
    renderRecentActivity(activityData) {
        const container = document.getElementById('recent-activity');
        if (!container) return;

        const activities = activityData.activities || [];
        
        const getActivityIcon = (type) => {
            switch (type) {
                case 'task_created': return 'plus-circle';
                case 'task_completed': return 'check-circle';
                case 'task_failed': return 'x-circle';
                case 'project_created': return 'folder-plus';
                case 'system_restart': return 'refresh-cw';
                default: return 'activity';
            }
        };

        const getActivityColor = (type) => {
            switch (type) {
                case 'task_created': return 'text-blue-600';
                case 'task_completed': return 'text-green-600';
                case 'task_failed': return 'text-red-600';
                case 'project_created': return 'text-purple-600';
                case 'system_restart': return 'text-yellow-600';
                default: return 'text-gray-600';
            }
        };

        const activityHtml = `
            <div class="card">
                <div class="card-header">
                    <h3 class="text-lg font-semibold text-gray-900">最近活动</h3>
                </div>
                <div class="card-body">
                    ${activities.length > 0 ? `
                        <div class="timeline">
                            ${activities.map(activity => `
                                <div class="timeline-item">
                                    <div class="timeline-marker ${getActivityColor(activity.type)}">
                                        <i data-lucide="${getActivityIcon(activity.type)}" class="w-3 h-3"></i>
                                    </div>
                                    <div class="timeline-content">
                                        <div class="flex justify-between items-start">
                                            <div>
                                                <div class="font-medium text-gray-900">${activity.title}</div>
                                                <div class="text-sm text-gray-600">${activity.description}</div>
                                            </div>
                                            <div class="text-xs text-gray-500">
                                                ${helpers.getRelativeTime(activity.timestamp)}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div class="empty-state">
                            <div class="empty-state-icon">
                                <i data-lucide="activity" class="w-12 h-12"></i>
                            </div>
                            <div class="empty-state-title">暂无活动记录</div>
                            <div class="empty-state-description">系统活动将在这里显示</div>
                        </div>
                    `}
                </div>
            </div>
        `;

        container.innerHTML = activityHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 渲染快速统计
     * @param {Object} quickStats - 快速统计数据
     */
    renderQuickStats(quickStats) {
        const container = document.getElementById('quick-stats');
        if (!container) return;

        const statsHtml = `
            <div class="card">
                <div class="card-header">
                    <h3 class="text-lg font-semibold text-gray-900">快速统计</h3>
                </div>
                <div class="card-body">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-600">${helpers.formatNumber(quickStats.today_tasks || 0)}</div>
                            <div class="text-sm text-gray-500">今日任务</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-green-600">${helpers.formatNumber(quickStats.success_rate || 0)}%</div>
                            <div class="text-sm text-gray-500">成功率</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-purple-600">${helpers.formatDuration(quickStats.avg_execution_time || 0)}</div>
                            <div class="text-sm text-gray-500">平均执行时间</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-yellow-600">${helpers.formatNumber(quickStats.active_projects || 0)}</div>
                            <div class="text-sm text-gray-500">活跃项目</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = statsHtml;
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-dashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData();
            });
        }

        // 自动刷新切换
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.autoRefreshEnabled = e.target.checked;
                if (this.autoRefreshEnabled) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }
    }

    /**
     * 开始自动刷新
     */
    startAutoRefresh() {
        if (!this.autoRefreshEnabled) return;
        
        this.stopAutoRefresh(); // 先停止现有的定时器
        
        this.refreshInterval = setInterval(() => {
            if (this.autoRefreshEnabled) {
                this.loadDashboardData();
            }
        }, this.refreshIntervalMs);
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
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('dashboard-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        // 可以集成到通知系统
        console.error('仪表板错误:', message);
        
        // 显示错误提示
        const errorContainer = document.getElementById('dashboard-error');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-danger">
                    <div class="flex items-center">
                        <i data-lucide="alert-circle" class="w-5 h-5 mr-2"></i>
                        <span>${message}</span>
                    </div>
                </div>
            `;
            errorContainer.style.display = 'block';
            
            // 重新初始化图标
            if (window.lucide) {
                window.lucide.createIcons();
            }
            
            // 5秒后自动隐藏
            setTimeout(() => {
                errorContainer.style.display = 'none';
            }, 5000);
        }
    }

    /**
     * 显示警告信息
     * @param {string} message - 警告信息
     */
    showWarning(message) {
        console.warn('仪表板警告:', message);
        
        const errorContainer = document.getElementById('dashboard-error');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-warning">
                    <div class="flex items-center">
                        <i data-lucide="alert-triangle" class="w-5 h-5 mr-2"></i>
                        <span>${message}</span>
                    </div>
                </div>
            `;
            errorContainer.style.display = 'block';
            
            if (window.lucide) {
                window.lucide.createIcons();
            }
            
            setTimeout(() => {
                errorContainer.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * 获取默认统计数据
     * @returns {Object} 默认统计数据
     */
    getDefaultStats() {
        return {
            total_tasks: 0,
            completed_tasks: 0,
            running_tasks: 0,
            total_projects: 0,
            tasks_change: 0,
            completed_change: 0,
            running_change: 0,
            projects_change: 0,
            task_status_distribution: {
                pending: 0,
                running: 0,
                completed: 0,
                failed: 0,
                cancelled: 0
            },
            hourly_activity: Array.from({ length: 24 }, (_, i) => ({ hour: i, count: 0 })),
            project_progress: []
        };
    }

    /**
     * 获取默认健康状态数据
     * @returns {Object} 默认健康状态数据
     */
    getDefaultHealth() {
        return {
            api_status: 'warning',
            database_status: 'warning',
            task_scheduler_status: 'warning',
            cpu_usage: 0,
            memory_usage: 0,
            disk_usage: 0,
            last_check: new Date().toISOString()
        };
    }

    /**
     * 获取默认快速统计数据
     * @returns {Object} 默认快速统计数据
     */
    getDefaultQuickStats() {
        return {
            today_tasks: 0,
            success_rate: 0,
            avg_execution_time: 0,
            active_projects: 0
        };
    }

    /**
     * 销毁仪表板
     */
    destroy() {
        this.stopAutoRefresh();
        
        // 销毁所有图表
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        
        this.charts = {};
    }

    /**
     * 获取仪表板HTML模板
     * @returns {string} HTML模板
     */
    static getTemplate() {
        return `
            <div class="dashboard-container">
                <!-- 错误提示 -->
                <div id="dashboard-error" style="display: none;"></div>
                
                <!-- 加载状态 -->
                <div id="dashboard-loading" class="text-center py-8" style="display: none;">
                    <div class="loading-dots">
                        <span style="--i: 0"></span>
                        <span style="--i: 1"></span>
                        <span style="--i: 2"></span>
                    </div>
                    <div class="mt-2 text-gray-600">加载中...</div>
                </div>
                
                <!-- 统计卡片 -->
                <div id="dashboard-stats" class="mb-8"></div>
                
                <!-- 图表区域 -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-8 mb-8">
                    <div class="chart-container">
                        <div class="chart-header">
                            <h3 class="chart-title text-base md:text-lg">任务状态分布</h3>
                        </div>
                        <div class="h-48 md:h-64">
                            <canvas id="task-status-chart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <div class="chart-header">
                            <h3 class="chart-title text-base md:text-lg">24小时活动趋势</h3>
                        </div>
                        <div class="h-48 md:h-64">
                            <canvas id="activity-trend-chart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- 项目进度图表 -->
                <div class="chart-container mb-8">
                    <div class="chart-header">
                        <h3 class="chart-title text-base md:text-lg">项目进度</h3>
                    </div>
                    <div class="h-48 md:h-64">
                        <canvas id="project-progress-chart"></canvas>
                    </div>
                </div>
                
                <!-- 系统健康状态和最近活动 -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-8">
                    <div id="system-health"></div>
                    <div id="recent-activity"></div>
                </div>
                
                <!-- 快速统计 -->
                <div id="quick-stats" class="mt-8"></div>
            </div>
        `;
    }
}

// 创建全局实例
const dashboard = new Dashboard();

// 导出到全局
window.dashboard = dashboard;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = dashboard;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return dashboard;
    });
}