/**
 * 项目管理组件
 * 提供项目的增删改查和设置功能
 */

class ProjectManager {
    constructor() {
        this.projects = [];
        this.currentPage = 1;
        this.pageSize = 20;
        this.totalPages = 1;
        this.totalItems = 0;
        this.filters = {
            search: ''
        };
        this.selectedProjects = new Set();
        this.sortBy = 'created_at';
        this.sortOrder = 'desc';
    }

    /**
     * 初始化项目管理器
     */
    async init() {
        console.log('初始化项目管理器...');
        this.setupEventListeners();
    }

    async render() {
        console.log('渲染项目管理器...');
        await this.loadProjects();
        this.renderProjects();
        this.renderPagination();
        this.updateProjectStats();
    }

    /**
     * 加载项目列表
     */
    async loadProjects() {
        this.showLoading(true);
        
        try {
            const params = {
                page: this.currentPage,
                size: this.pageSize,
                ...this.filters
            };
            
            // 移除空值
            Object.keys(params).forEach(key => {
                if (params[key] === '' || params[key] === null || params[key] === undefined) {
                    delete params[key];
                }
            });

            const result = await api.getProjects(params);
            
            if (result.success) {
                this.projects = result.data.items || [];
                this.totalPages = result.data.pagination?.total_pages || 1;
                this.totalItems = result.data.pagination?.total_items || 0;
                this.currentPage = result.data.pagination?.current_page || 1;
                
                this.render();
            } else {
                console.error('加载项目列表失败:', result.error);
                this.showError('加载项目列表失败: ' + result.error);
            }
        } catch (error) {
            console.error('加载项目列表失败:', error);
            this.showError('加载项目列表失败，请检查网络连接');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * 渲染项目列表
     */
    renderProjects() {
        const container = document.getElementById('projects-list');
        if (!container) return;

        if (this.projects.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <i data-lucide="folder" class="w-12 h-12"></i>
                    </div>
                    <div class="empty-state-title">暂无项目</div>
                    <div class="empty-state-description">点击"创建项目"按钮开始添加项目</div>
                    <button class="btn btn-primary mt-4" onclick="projectManager.showCreateProjectModal()">
                        <i data-lucide="plus" class="w-4 h-4 mr-2"></i>
                        创建项目
                    </button>
                </div>
            `;
            
            if (window.lucide) {
                window.lucide.createIcons();
            }
            return;
        }

        const projectsHtml = `
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
                ${this.projects.map(project => this.renderProjectCard(project)).join('')}
            </div>
        `;

        container.innerHTML = projectsHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 渲染单个项目卡片
     * @param {Object} project - 项目对象
     * @returns {string} HTML字符串
     */
    renderProjectCard(project) {
        const isSelected = this.selectedProjects.has(project.id);
        
        return `
            <div class="card project-card ${isSelected ? 'selected' : ''}" data-project-id="${project.id}">
                <div class="card-body">
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex items-center space-x-3">
                            <input type="checkbox" 
                                   ${isSelected ? 'checked' : ''}
                                   onchange="projectManager.toggleProjectSelection(${project.id}, this.checked)"
                                   class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                            <div class="project-icon">
                                <i data-lucide="folder" class="w-8 h-8 text-blue-600"></i>
                            </div>
                        </div>
                        <div class="dropdown">
                            <button class="btn btn-sm btn-ghost" onclick="projectManager.toggleProjectMenu(${project.id})">
                                <i data-lucide="more-vertical" class="w-4 h-4"></i>
                            </button>
                            <div class="dropdown-menu" id="project-menu-${project.id}" style="display: none;">
                                <a href="#" onclick="projectManager.viewProject(${project.id})" class="dropdown-item">
                                    <i data-lucide="eye" class="w-4 h-4 mr-2"></i>
                                    查看详情
                                </a>
                                <a href="#" onclick="projectManager.editProject(${project.id})" class="dropdown-item">
                                    <i data-lucide="edit" class="w-4 h-4 mr-2"></i>
                                    编辑项目
                                </a>
                                <a href="#" onclick="projectManager.projectSettings(${project.id})" class="dropdown-item">
                                    <i data-lucide="settings" class="w-4 h-4 mr-2"></i>
                                    项目设置
                                </a>
                                <a href="#" onclick="projectManager.scanProject(${project.id})" class="dropdown-item">
                                    <i data-lucide="search" class="w-4 h-4 mr-2"></i>
                                    扫描项目
                                </a>
                                <div class="dropdown-divider"></div>
                                <a href="#" onclick="projectManager.deleteProject(${project.id})" class="dropdown-item text-red-600">
                                    <i data-lucide="trash-2" class="w-4 h-4 mr-2"></i>
                                    删除项目
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <h3 class="text-base md:text-lg font-semibold text-gray-900 mb-2 truncate">${project.name}</h3>
                        <p class="text-xs md:text-sm text-gray-600 line-clamp-2">${project.description || '无描述'}</p>
                    </div>
                    
                    <div class="space-y-3">
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">任务数量</span>
                            <span class="font-medium">${project.task_count || 0}</span>
                        </div>
                        
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">数据源</span>
                            <span class="font-medium">${project.source_count || 0}</span>
                        </div>
                        
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">创建时间</span>
                            <span class="font-medium">${helpers.formatDate(project.created_at)}</span>
                        </div>
                        
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">最后更新</span>
                            <span class="font-medium">${helpers.getRelativeTime(project.updated_at)}</span>
                        </div>
                    </div>
                    
                    <div class="mt-4 pt-4 border-t border-gray-200">
                        <div class="flex items-center space-x-2">
                            <button class="btn btn-sm btn-primary flex-1 text-xs md:text-sm" 
                                    onclick="projectManager.viewProjectTasks(${project.id})">
                                <i data-lucide="list" class="w-3 h-3 md:w-4 md:h-4 mr-1"></i>
                                <span class="hidden sm:inline">查看任务</span>
                                <span class="sm:hidden">任务</span>
                            </button>
                            <button class="btn btn-sm btn-outline" 
                                    onclick="projectManager.projectAnalytics(${project.id})">
                                <i data-lucide="bar-chart-3" class="w-3 h-3 md:w-4 md:h-4"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 渲染分页
     */
    renderPagination() {
        const container = document.getElementById('projects-pagination');
        if (!container) return;

        if (this.totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        const startItem = (this.currentPage - 1) * this.pageSize + 1;
        const endItem = Math.min(this.currentPage * this.pageSize, this.totalItems);

        const paginationHtml = `
            <div class="pagination">
                <div class="pagination-info">
                    显示 ${startItem}-${endItem} 项，共 ${this.totalItems} 项
                </div>
                <div class="pagination-nav">
                    <button class="pagination-btn" 
                            ${this.currentPage <= 1 ? 'disabled' : ''}
                            onclick="projectManager.goToPage(${this.currentPage - 1})">
                        <i data-lucide="chevron-left" class="w-4 h-4"></i>
                    </button>
                    
                    ${this.generatePageNumbers()}
                    
                    <button class="pagination-btn" 
                            ${this.currentPage >= this.totalPages ? 'disabled' : ''}
                            onclick="projectManager.goToPage(${this.currentPage + 1})">
                        <i data-lucide="chevron-right" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
        `;

        container.innerHTML = paginationHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 生成页码
     * @returns {string} HTML字符串
     */
    generatePageNumbers() {
        const pages = [];
        const maxVisible = 5;
        let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(this.totalPages, start + maxVisible - 1);
        
        if (end - start + 1 < maxVisible) {
            start = Math.max(1, end - maxVisible + 1);
        }
        
        for (let i = start; i <= end; i++) {
            pages.push(`
                <button class="pagination-btn ${i === this.currentPage ? 'active' : ''}" 
                        onclick="projectManager.goToPage(${i})">
                    ${i}
                </button>
            `);
        }
        
        return pages.join('');
    }

    /**
     * 更新项目统计
     */
    updateProjectStats() {
        const statsContainer = document.getElementById('project-stats');
        if (!statsContainer) return;

        const stats = {
            total: this.totalItems,
            selected: this.selectedProjects.size
        };

        const statsHtml = `
            <div class="flex items-center space-x-6 text-sm text-gray-600">
                <span>总计: <strong class="text-gray-900">${stats.total}</strong></span>
                ${stats.selected > 0 ? `<span>已选择: <strong class="text-blue-600">${stats.selected}</strong></span>` : ''}
            </div>
        `;

        statsContainer.innerHTML = statsHtml;
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 搜索框
        const searchInput = document.getElementById('project-search');
        if (searchInput) {
            searchInput.addEventListener('input', helpers.debounce((e) => {
                this.filters.search = e.target.value;
                this.currentPage = 1;
                this.loadProjects();
            }, 500));
        }

        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-projects');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadProjects();
            });
        }

        // 创建项目按钮
        const createBtn = document.getElementById('create-project-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                this.showCreateProjectModal();
            });
        }

        // 批量操作按钮
        const bulkActionBtn = document.getElementById('bulk-project-action-btn');
        if (bulkActionBtn) {
            bulkActionBtn.addEventListener('click', () => {
                this.showBulkActionModal();
            });
        }

        // 点击外部关闭下拉菜单
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown')) {
                this.closeAllProjectMenus();
            }
        });
    }

    /**
     * 跳转到指定页面
     * @param {number} page - 页码
     */
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) {
            return;
        }
        
        this.currentPage = page;
        this.loadProjects();
    }

    /**
     * 切换项目选择
     * @param {number} projectId - 项目ID
     * @param {boolean} checked - 是否选中
     */
    toggleProjectSelection(projectId, checked) {
        if (checked) {
            this.selectedProjects.add(projectId);
        } else {
            this.selectedProjects.delete(projectId);
        }
        
        this.updateProjectStats();
        this.updateBulkActionButton();
        
        // 更新卡片样式
        const card = document.querySelector(`[data-project-id="${projectId}"]`);
        if (card) {
            if (checked) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        }
    }

    /**
     * 更新批量操作按钮状态
     */
    updateBulkActionButton() {
        const bulkActionBtn = document.getElementById('bulk-project-action-btn');
        if (bulkActionBtn) {
            bulkActionBtn.disabled = this.selectedProjects.size === 0;
            bulkActionBtn.textContent = `批量操作 (${this.selectedProjects.size})`;
        }
    }

    /**
     * 切换项目菜单
     * @param {number} projectId - 项目ID
     */
    toggleProjectMenu(projectId) {
        this.closeAllProjectMenus();
        
        const menu = document.getElementById(`project-menu-${projectId}`);
        if (menu) {
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        }
    }

    /**
     * 关闭所有项目菜单
     */
    closeAllProjectMenus() {
        const menus = document.querySelectorAll('[id^="project-menu-"]');
        menus.forEach(menu => {
            menu.style.display = 'none';
        });
    }

    /**
     * 查看项目详情
     * @param {number} projectId - 项目ID
     */
    async viewProject(projectId) {
        this.closeAllProjectMenus();
        
        try {
            const result = await api.getProject(projectId);
            if (result.success) {
                this.showProjectDetailModal(result.data);
            } else {
                this.showError('获取项目详情失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取项目详情失败:', error);
            this.showError('获取项目详情失败，请重试');
        }
    }

    /**
     * 编辑项目
     * @param {number} projectId - 项目ID
     */
    async editProject(projectId) {
        this.closeAllProjectMenus();
        
        try {
            const result = await api.getProject(projectId);
            if (result.success) {
                this.showEditProjectModal(result.data);
            } else {
                this.showError('获取项目信息失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取项目信息失败:', error);
            this.showError('获取项目信息失败，请重试');
        }
    }

    /**
     * 项目设置
     * @param {number} projectId - 项目ID
     */
    async projectSettings(projectId) {
        this.closeAllProjectMenus();
        
        try {
            const result = await api.getProjectSettings(projectId);
            if (result.success) {
                this.showProjectSettingsModal(projectId, result.data);
            } else {
                this.showError('获取项目设置失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取项目设置失败:', error);
            this.showError('获取项目设置失败，请重试');
        }
    }

    /**
     * 扫描项目
     * @param {number} projectId - 项目ID
     */
    async scanProject(projectId) {
        this.closeAllProjectMenus();
        
        if (!confirm('确定要扫描这个项目吗？这可能需要一些时间。')) {
            return;
        }
        
        try {
            const result = await api.scanProject(projectId);
            if (result.success) {
                this.showSuccess('项目扫描已开始');
                this.loadProjects();
            } else {
                this.showError('项目扫描失败: ' + result.error);
            }
        } catch (error) {
            console.error('项目扫描失败:', error);
            this.showError('项目扫描失败，请重试');
        }
    }

    /**
     * 删除项目
     * @param {number} projectId - 项目ID
     */
    async deleteProject(projectId) {
        this.closeAllProjectMenus();
        
        if (!confirm('确定要删除这个项目吗？此操作不可恢复，项目下的所有任务也将被删除。')) {
            return;
        }
        
        try {
            const result = await api.deleteProject(projectId);
            if (result.success) {
                this.showSuccess('项目删除成功');
                this.loadProjects();
            } else {
                this.showError('项目删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('项目删除失败:', error);
            this.showError('项目删除失败，请重试');
        }
    }

    /**
     * 查看项目任务
     * @param {number} projectId - 项目ID
     */
    viewProjectTasks(projectId) {
        // 切换到任务管理页面，并设置项目过滤器
        if (window.app && window.app.showView) {
            window.app.showView('tasks');
            
            // 等待任务管理器加载完成后设置过滤器
            setTimeout(() => {
                if (window.taskManager) {
                    const projectFilter = document.getElementById('project-filter');
                    if (projectFilter) {
                        projectFilter.value = projectId;
                        projectFilter.dispatchEvent(new Event('change'));
                    }
                }
            }, 100);
        }
    }

    /**
     * 项目分析
     * @param {number} projectId - 项目ID
     */
    async projectAnalytics(projectId) {
        try {
            const result = await api.getProjectAnalytics(projectId);
            if (result.success) {
                this.showProjectAnalyticsModal(projectId, result.data);
            } else {
                this.showError('获取项目分析失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取项目分析失败:', error);
            this.showError('获取项目分析失败，请重试');
        }
    }

    /**
     * 显示创建项目模态框
     */
    showCreateProjectModal() {
        const modal = document.getElementById('project-modal');
        const form = document.getElementById('project-form');
        const title = document.getElementById('project-modal-title');
        
        if (!modal || !form || !title) return;
        
        title.textContent = '创建项目';
        form.reset();
        form.dataset.mode = 'create';
        
        modal.style.display = 'flex';
    }

    /**
     * 显示编辑项目模态框
     * @param {Object} project - 项目对象
     */
    showEditProjectModal(project) {
        const modal = document.getElementById('project-modal');
        const form = document.getElementById('project-form');
        const title = document.getElementById('project-modal-title');
        
        if (!modal || !form || !title) return;
        
        title.textContent = '编辑项目';
        form.dataset.mode = 'edit';
        form.dataset.projectId = project.id;
        
        // 填充表单数据
        form.querySelector('#project-name').value = project.name || '';
        form.querySelector('#project-description').value = project.description || '';
        
        modal.style.display = 'flex';
    }

    /**
     * 显示项目详情模态框
     * @param {Object} project - 项目对象
     */
    showProjectDetailModal(project) {
        const modal = document.getElementById('project-detail-modal');
        const content = document.getElementById('project-detail-content');
        
        if (!modal || !content) return;
        
        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">项目名称</label>
                        <div class="text-gray-900 font-medium">${project.name}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">创建时间</label>
                        <div class="text-gray-900">${helpers.formatDate(project.created_at)}</div>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">项目描述</label>
                    <div class="text-gray-900 whitespace-pre-wrap">${project.description || '无描述'}</div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="stat-card">
                        <div class="stat-value">${project.task_count || 0}</div>
                        <div class="stat-label">任务数量</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${project.source_count || 0}</div>
                        <div class="stat-label">数据源</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${helpers.getRelativeTime(project.updated_at)}</div>
                        <div class="stat-label">最后更新</div>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.display = 'flex';
    }

    /**
     * 显示项目设置模态框
     * @param {number} projectId - 项目ID
     * @param {Object} settings - 设置对象
     */
    showProjectSettingsModal(projectId, settings) {
        const modal = document.getElementById('project-settings-modal');
        const form = document.getElementById('project-settings-form');
        
        if (!modal || !form) return;
        
        form.dataset.projectId = projectId;
        
        // 填充设置数据
        const settingsJson = JSON.stringify(settings || {}, null, 2);
        form.querySelector('#project-settings-json').value = settingsJson;
        
        modal.style.display = 'flex';
    }

    /**
     * 显示项目分析模态框
     * @param {number} projectId - 项目ID
     * @param {Object} analytics - 分析数据
     */
    showProjectAnalyticsModal(projectId, analytics) {
        const modal = document.getElementById('project-analytics-modal');
        const content = document.getElementById('project-analytics-content');
        
        if (!modal || !content) return;
        
        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div class="stat-card">
                        <div class="stat-value">${analytics.total_tasks || 0}</div>
                        <div class="stat-label">总任务数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${analytics.completed_tasks || 0}</div>
                        <div class="stat-label">已完成</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${analytics.failed_tasks || 0}</div>
                        <div class="stat-label">失败任务</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${analytics.success_rate || 0}%</div>
                        <div class="stat-label">成功率</div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <canvas id="project-analytics-chart-${projectId}" width="400" height="200"></canvas>
                </div>
            </div>
        `;
        
        modal.style.display = 'flex';
        
        // 渲染图表
        this.renderAnalyticsChart(projectId, analytics);
    }

    /**
     * 渲染分析图表
     * @param {number} projectId - 项目ID
     * @param {Object} analytics - 分析数据
     */
    renderAnalyticsChart(projectId, analytics) {
        const canvas = document.getElementById(`project-analytics-chart-${projectId}`);
        if (!canvas || !window.Chart) return;
        
        const ctx = canvas.getContext('2d');
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['已完成', '运行中', '待执行', '失败'],
                datasets: [{
                    data: [
                        analytics.completed_tasks || 0,
                        analytics.running_tasks || 0,
                        analytics.pending_tasks || 0,
                        analytics.failed_tasks || 0
                    ],
                    backgroundColor: [
                        '#10B981',
                        '#3B82F6',
                        '#F59E0B',
                        '#EF4444'
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
    }

    /**
     * 显示批量操作模态框
     */
    showBulkActionModal() {
        if (this.selectedProjects.size === 0) {
            this.showError('请先选择要操作的项目');
            return;
        }
        
        const modal = document.getElementById('bulk-project-action-modal');
        if (!modal) return;
        
        modal.style.display = 'flex';
    }

    /**
     * 执行批量操作
     * @param {string} action - 操作类型
     */
    async executeBulkAction(action) {
        if (this.selectedProjects.size === 0) {
            this.showError('请先选择要操作的项目');
            return;
        }
        
        const actionNames = {
            delete: '删除',
            scan: '扫描'
        };
        
        const actionName = actionNames[action] || action;
        
        if (!confirm(`确定要${actionName}选中的 ${this.selectedProjects.size} 个项目吗？`)) {
            return;
        }
        
        try {
            // 这里需要根据实际API实现批量操作
            const promises = Array.from(this.selectedProjects).map(projectId => {
                switch (action) {
                    case 'delete':
                        return api.deleteProject(projectId);
                    case 'scan':
                        return api.scanProject(projectId);
                    default:
                        return Promise.resolve({ success: false, error: '未知操作' });
                }
            });
            
            const results = await Promise.all(promises);
            const successCount = results.filter(r => r.success).length;
            const failCount = results.length - successCount;
            
            if (successCount > 0) {
                this.showSuccess(`批量${actionName}操作完成：成功 ${successCount} 个，失败 ${failCount} 个`);
                this.selectedProjects.clear();
                this.loadProjects();
                this.closeBulkActionModal();
            } else {
                this.showError(`批量${actionName}操作失败`);
            }
        } catch (error) {
            console.error(`批量${actionName}操作失败:`, error);
            this.showError(`批量${actionName}操作失败，请重试`);
        }
    }

    /**
     * 关闭批量操作模态框
     */
    closeBulkActionModal() {
        const modal = document.getElementById('bulk-project-action-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('projects-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        console.error('项目管理错误:', message);
        // 这里可以集成到全局通知系统
        alert('错误: ' + message);
    }

    /**
     * 显示成功信息
     * @param {string} message - 成功信息
     */
    showSuccess(message) {
        console.log('项目管理成功:', message);
        // 这里可以集成到全局通知系统
        alert('成功: ' + message);
    }

    /**
     * 获取项目管理HTML模板
     * @returns {string} HTML模板
     */
    static getTemplate() {
        return `
            <div class="project-manager-container">
                <!-- 工具栏 -->
                <div class="card mb-6">
                    <div class="card-body">
                        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
                            <div class="flex flex-col sm:flex-row sm:items-center space-y-2 sm:space-y-0 sm:space-x-2 md:space-x-4">
                                <div class="search-box">
                                    <i data-lucide="search" class="search-icon"></i>
                                    <input type="text" id="project-search" class="search-input" placeholder="搜索项目...">
                                </div>
                            </div>
                            
                            <div class="flex items-center space-x-2 md:space-x-3">
                                <button id="bulk-project-action-btn" class="btn btn-outline text-xs md:text-sm" disabled>
                                    <span class="hidden sm:inline">批量操作 (0)</span>
                                    <span class="sm:hidden">批量 (0)</span>
                                </button>
                                <button id="refresh-projects" class="btn btn-outline">
                                    <i data-lucide="refresh-cw" class="w-3 h-3 md:w-4 md:h-4 mr-1 md:mr-2"></i>
                                    <span class="hidden sm:inline">刷新</span>
                                </button>
                                <button id="create-project-btn" class="btn btn-primary">
                                    <i data-lucide="plus" class="w-3 h-3 md:w-4 md:h-4 mr-1 md:mr-2"></i>
                                    <span class="hidden sm:inline">创建项目</span>
                                    <span class="sm:hidden">创建</span>
                                </button>
                            </div>
                        </div>
                        
                        <!-- 统计信息 -->
                        <div id="project-stats" class="mt-4 pt-4 border-t border-gray-200"></div>
                    </div>
                </div>
                
                <!-- 加载状态 -->
                <div id="projects-loading" class="text-center py-8" style="display: none;">
                    <div class="loading-dots">
                        <span style="--i: 0"></span>
                        <span style="--i: 1"></span>
                        <span style="--i: 2"></span>
                    </div>
                    <div class="mt-2 text-gray-600">加载中...</div>
                </div>
                
                <!-- 项目列表 -->
                <div id="projects-list"></div>
                
                <!-- 分页 -->
                <div id="projects-pagination" class="mt-6"></div>
            </div>
        `;
    }
}

// 创建全局实例
const projectManager = new ProjectManager();

// 导出到全局
window.projectManager = projectManager;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = projectManager;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return projectManager;
    });
}