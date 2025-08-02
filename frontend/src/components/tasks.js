/**
 * 任务管理组件
 * 提供任务的增删改查和执行功能
 */

class TaskManager {
    constructor() {
        this.tasks = [];
        this.projects = [];
        this.currentPage = 1;
        this.pageSize = 20;
        this.totalPages = 1;
        this.totalItems = 0;
        this.filters = {
            status: '',
            project_id: '',
            search: ''
        };
        this.selectedTasks = new Set();
        this.sortBy = 'created_at';
        this.sortOrder = 'desc';
    }

    /**
     * 初始化任务管理器
     */
    async init() {
        console.log('初始化任务管理器...');
        this.setupEventListeners();
        await this.loadProjects();
        await this.loadTasks();
    }

    async render() {
        console.log('渲染任务管理器...');
        this.renderTasks();
        this.renderPagination();
        this.updateTaskStats();
        this.renderProjectFilter();
    }

    /**
     * 加载项目列表
     */
    async loadProjects() {
        try {
            const result = await api.getProjects({ size: 100 });
            if (result.success) {
                this.projects = result.data.items || [];
                this.renderProjectFilter();
            } else {
                console.error('加载项目列表失败:', result.error);
            }
        } catch (error) {
            console.error('加载项目列表失败:', error);
        }
    }

    /**
     * 加载任务列表
     */
    async loadTasks() {
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

            const result = await api.getTasks(params);
            
            if (result.success) {
                this.tasks = result.data.items || [];
                this.totalPages = result.data.pagination?.total_pages || 1;
                this.totalItems = result.data.pagination?.total_items || 0;
                this.currentPage = result.data.pagination?.current_page || 1;
                
                this.render();
            } else {
                console.error('加载任务列表失败:', result.error);
                this.showError('加载任务列表失败: ' + result.error);
            }
        } catch (error) {
            console.error('加载任务列表失败:', error);
            this.showError('加载任务列表失败，请检查网络连接');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * 渲染项目过滤器
     */
    renderProjectFilter() {
        const projectFilter = document.getElementById('project-filter');
        if (!projectFilter) return;

        const options = this.projects.map(project => 
            `<option value="${project.id}">${project.name}</option>`
        ).join('');

        projectFilter.innerHTML = `
            <option value="">所有项目</option>
            ${options}
        `;
    }

    /**
     * 渲染任务列表
     */
    renderTasks() {
        const container = document.getElementById('tasks-list');
        if (!container) return;

        if (this.tasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <i data-lucide="clipboard-list" class="w-12 h-12"></i>
                    </div>
                    <div class="empty-state-title">暂无任务</div>
                    <div class="empty-state-description">点击"创建任务"按钮开始添加任务</div>
                    <button class="btn btn-primary mt-4" onclick="taskManager.showCreateTaskModal()">
                        <i data-lucide="plus" class="w-4 h-4 mr-2"></i>
                        创建任务
                    </button>
                </div>
            `;
            
            if (window.lucide) {
                window.lucide.createIcons();
            }
            return;
        }

        const tasksHtml = `
            <div class="card">
                <div class="card-body p-0">
                    <div class="overflow-x-auto">
                        <table class="table table-responsive">
                            <thead>
                                <tr>
                                    <th class="w-12">
                                        <input type="checkbox" id="select-all-tasks" 
                                               onchange="taskManager.toggleSelectAll(this.checked)" 
                                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                                    </th>
                                    <th class="cursor-pointer min-w-48" onclick="taskManager.sortTasks('name')">
                                        任务名称
                                        ${this.getSortIcon('name')}
                                    </th>
                                    <th class="cursor-pointer hidden sm:table-cell" onclick="taskManager.sortTasks('project_id')">
                                        项目
                                        ${this.getSortIcon('project_id')}
                                    </th>
                                    <th class="cursor-pointer" onclick="taskManager.sortTasks('status')">
                                        状态
                                        ${this.getSortIcon('status')}
                                    </th>
                                    <th class="cursor-pointer hidden md:table-cell" onclick="taskManager.sortTasks('created_at')">
                                        创建时间
                                        ${this.getSortIcon('created_at')}
                                    </th>
                                    <th class="cursor-pointer hidden lg:table-cell" onclick="taskManager.sortTasks('updated_at')">
                                        更新时间
                                        ${this.getSortIcon('updated_at')}
                                    </th>
                                    <th class="min-w-32">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${this.tasks.map(task => this.renderTaskRow(task)).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = tasksHtml;
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 渲染单个任务行
     * @param {Object} task - 任务对象
     * @returns {string} HTML字符串
     */
    renderTaskRow(task) {
        const project = this.projects.find(p => p.id === task.project_id);
        const projectName = project ? project.name : '未知项目';
        
        return `
            <tr class="hover:bg-gray-50 ${this.selectedTasks.has(task.id) ? 'bg-blue-50' : ''}">
                <td>
                    <input type="checkbox" 
                           ${this.selectedTasks.has(task.id) ? 'checked' : ''}
                           onchange="taskManager.toggleTaskSelection(${task.id}, this.checked)"
                           class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                </td>
                <td>
                    <div class="font-medium text-gray-900 text-sm md:text-base">${task.name}</div>
                    <div class="text-xs md:text-sm text-gray-500">${helpers.truncateText(task.description || '', 50)}</div>
                    <div class="sm:hidden mt-1">
                        <span class="tag tag-secondary text-xs">${projectName}</span>
                    </div>
                </td>
                <td class="hidden sm:table-cell">
                    <span class="tag tag-secondary">${projectName}</span>
                </td>
                <td>
                    ${this.getStatusBadge(task.status)}
                </td>
                <td class="hidden md:table-cell text-sm text-gray-500">
                    ${helpers.formatDate(task.created_at)}
                </td>
                <td class="hidden lg:table-cell text-sm text-gray-500">
                    ${helpers.formatDate(task.updated_at)}
                </td>
                <td>
                    <div class="flex items-center space-x-1 md:space-x-2">
                        <button class="btn btn-sm btn-outline" 
                                onclick="taskManager.viewTask(${task.id})"
                                title="查看详情">
                            <i data-lucide="eye" class="w-3 h-3 md:w-4 md:h-4"></i>
                        </button>
                        
                        ${task.status === 'pending' ? `
                            <button class="btn btn-sm btn-success" 
                                    onclick="taskManager.executeTask(${task.id})"
                                    title="执行任务">
                                <i data-lucide="play" class="w-3 h-3 md:w-4 md:h-4"></i>
                            </button>
                        ` : ''}
                        
                        ${task.status === 'running' ? `
                            <button class="btn btn-sm btn-warning" 
                                    onclick="taskManager.cancelTask(${task.id})"
                                    title="取消任务">
                                <i data-lucide="square" class="w-3 h-3 md:w-4 md:h-4"></i>
                            </button>
                        ` : ''}
                        
                        <button class="btn btn-sm btn-outline hidden md:inline-flex" 
                                onclick="taskManager.editTask(${task.id})"
                                title="编辑任务">
                            <i data-lucide="edit" class="w-3 h-3 md:w-4 md:h-4"></i>
                        </button>
                        
                        <button class="btn btn-sm btn-danger" 
                                onclick="taskManager.deleteTask(${task.id})"
                                title="删除任务">
                            <i data-lucide="trash-2" class="w-3 h-3 md:w-4 md:h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }

    /**
     * 获取状态徽章
     * @param {string} status - 状态
     * @returns {string} HTML字符串
     */
    getStatusBadge(status) {
        const statusConfig = {
            pending: { class: 'badge-warning', text: '待执行', icon: 'clock' },
            running: { class: 'badge-info', text: '运行中', icon: 'play-circle' },
            completed: { class: 'badge-success', text: '已完成', icon: 'check-circle' },
            failed: { class: 'badge-danger', text: '失败', icon: 'x-circle' },
            cancelled: { class: 'badge-secondary', text: '已取消', icon: 'minus-circle' }
        };
        
        const config = statusConfig[status] || statusConfig.pending;
        
        return `
            <span class="badge ${config.class}">
                <i data-lucide="${config.icon}" class="w-3 h-3 mr-1"></i>
                ${config.text}
            </span>
        `;
    }

    /**
     * 获取排序图标
     * @param {string} field - 字段名
     * @returns {string} HTML字符串
     */
    getSortIcon(field) {
        if (this.sortBy !== field) {
            return '<i data-lucide="chevrons-up-down" class="w-4 h-4 inline ml-1 text-gray-400"></i>';
        }
        
        const icon = this.sortOrder === 'asc' ? 'chevron-up' : 'chevron-down';
        return `<i data-lucide="${icon}" class="w-4 h-4 inline ml-1 text-blue-600"></i>`;
    }

    /**
     * 渲染分页
     */
    renderPagination() {
        const container = document.getElementById('tasks-pagination');
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
                            onclick="taskManager.goToPage(${this.currentPage - 1})">
                        <i data-lucide="chevron-left" class="w-4 h-4"></i>
                    </button>
                    
                    ${this.generatePageNumbers()}
                    
                    <button class="pagination-btn" 
                            ${this.currentPage >= this.totalPages ? 'disabled' : ''}
                            onclick="taskManager.goToPage(${this.currentPage + 1})">
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
                        onclick="taskManager.goToPage(${i})">
                    ${i}
                </button>
            `);
        }
        
        return pages.join('');
    }

    /**
     * 更新任务统计
     */
    updateTaskStats() {
        const statsContainer = document.getElementById('task-stats');
        if (!statsContainer) return;

        const stats = {
            total: this.totalItems,
            selected: this.selectedTasks.size,
            pending: this.tasks.filter(t => t.status === 'pending').length,
            running: this.tasks.filter(t => t.status === 'running').length,
            completed: this.tasks.filter(t => t.status === 'completed').length,
            failed: this.tasks.filter(t => t.status === 'failed').length
        };

        const statsHtml = `
            <div class="flex items-center space-x-6 text-sm text-gray-600">
                <span>总计: <strong class="text-gray-900">${stats.total}</strong></span>
                ${stats.selected > 0 ? `<span>已选择: <strong class="text-blue-600">${stats.selected}</strong></span>` : ''}
                <span>待执行: <strong class="text-yellow-600">${stats.pending}</strong></span>
                <span>运行中: <strong class="text-blue-600">${stats.running}</strong></span>
                <span>已完成: <strong class="text-green-600">${stats.completed}</strong></span>
                <span>失败: <strong class="text-red-600">${stats.failed}</strong></span>
            </div>
        `;

        statsContainer.innerHTML = statsHtml;
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 搜索框
        const searchInput = document.getElementById('task-search');
        if (searchInput) {
            searchInput.addEventListener('input', helpers.debounce((e) => {
                this.filters.search = e.target.value;
                this.currentPage = 1;
                this.loadTasks();
            }, 500));
        }

        // 状态过滤器
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filters.status = e.target.value;
                this.currentPage = 1;
                this.loadTasks();
            });
        }

        // 项目过滤器
        const projectFilter = document.getElementById('project-filter');
        if (projectFilter) {
            projectFilter.addEventListener('change', (e) => {
                this.filters.project_id = e.target.value;
                this.currentPage = 1;
                this.loadTasks();
            });
        }

        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-tasks');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadTasks();
            });
        }

        // 创建任务按钮
        const createBtn = document.getElementById('create-task-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                this.showCreateTaskModal();
            });
        }

        // 批量操作按钮
        const bulkActionBtn = document.getElementById('bulk-action-btn');
        if (bulkActionBtn) {
            bulkActionBtn.addEventListener('click', () => {
                this.showBulkActionModal();
            });
        }
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
        this.loadTasks();
    }

    /**
     * 排序任务
     * @param {string} field - 排序字段
     */
    sortTasks(field) {
        if (this.sortBy === field) {
            this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortBy = field;
            this.sortOrder = 'asc';
        }
        
        this.currentPage = 1;
        this.loadTasks();
    }

    /**
     * 切换全选
     * @param {boolean} checked - 是否选中
     */
    toggleSelectAll(checked) {
        if (checked) {
            this.tasks.forEach(task => this.selectedTasks.add(task.id));
        } else {
            this.selectedTasks.clear();
        }
        
        this.renderTasks();
        this.updateTaskStats();
        this.updateBulkActionButton();
    }

    /**
     * 切换任务选择
     * @param {number} taskId - 任务ID
     * @param {boolean} checked - 是否选中
     */
    toggleTaskSelection(taskId, checked) {
        if (checked) {
            this.selectedTasks.add(taskId);
        } else {
            this.selectedTasks.delete(taskId);
        }
        
        this.updateTaskStats();
        this.updateBulkActionButton();
        
        // 更新全选复选框状态
        const selectAllCheckbox = document.getElementById('select-all-tasks');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = this.selectedTasks.size === this.tasks.length;
            selectAllCheckbox.indeterminate = this.selectedTasks.size > 0 && this.selectedTasks.size < this.tasks.length;
        }
    }

    /**
     * 更新批量操作按钮状态
     */
    updateBulkActionButton() {
        const bulkActionBtn = document.getElementById('bulk-action-btn');
        if (bulkActionBtn) {
            bulkActionBtn.disabled = this.selectedTasks.size === 0;
            bulkActionBtn.textContent = `批量操作 (${this.selectedTasks.size})`;
        }
    }

    /**
     * 查看任务详情
     * @param {number} taskId - 任务ID
     */
    async viewTask(taskId) {
        try {
            const result = await api.getTask(taskId);
            if (result.success) {
                this.showTaskDetailModal(result.data);
            } else {
                this.showError('获取任务详情失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取任务详情失败:', error);
            this.showError('获取任务详情失败，请重试');
        }
    }

    /**
     * 执行任务
     * @param {number} taskId - 任务ID
     */
    async executeTask(taskId) {
        try {
            const result = await api.executeTask(taskId);
            if (result.success) {
                this.showSuccess('任务执行成功');
                this.loadTasks();
            } else {
                this.showError('任务执行失败: ' + result.error);
            }
        } catch (error) {
            console.error('任务执行失败:', error);
            this.showError('任务执行失败，请重试');
        }
    }

    /**
     * 取消任务
     * @param {number} taskId - 任务ID
     */
    async cancelTask(taskId) {
        if (!confirm('确定要取消这个任务吗？')) {
            return;
        }
        
        try {
            const result = await api.cancelTask(taskId);
            if (result.success) {
                this.showSuccess('任务取消成功');
                this.loadTasks();
            } else {
                this.showError('任务取消失败: ' + result.error);
            }
        } catch (error) {
            console.error('任务取消失败:', error);
            this.showError('任务取消失败，请重试');
        }
    }

    /**
     * 编辑任务
     * @param {number} taskId - 任务ID
     */
    async editTask(taskId) {
        try {
            const result = await api.getTask(taskId);
            if (result.success) {
                this.showEditTaskModal(result.data);
            } else {
                this.showError('获取任务信息失败: ' + result.error);
            }
        } catch (error) {
            console.error('获取任务信息失败:', error);
            this.showError('获取任务信息失败，请重试');
        }
    }

    /**
     * 删除任务
     * @param {number} taskId - 任务ID
     */
    async deleteTask(taskId) {
        if (!confirm('确定要删除这个任务吗？此操作不可恢复。')) {
            return;
        }
        
        try {
            const result = await api.deleteTask(taskId);
            if (result.success) {
                this.showSuccess('任务删除成功');
                this.loadTasks();
            } else {
                this.showError('任务删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('任务删除失败:', error);
            this.showError('任务删除失败，请重试');
        }
    }

    /**
     * 显示创建任务模态框
     */
    showCreateTaskModal() {
        const modal = document.getElementById('task-modal');
        const form = document.getElementById('task-form');
        const title = document.getElementById('task-modal-title');
        
        if (!modal || !form || !title) return;
        
        title.textContent = '创建任务';
        form.reset();
        form.dataset.mode = 'create';
        
        // 填充项目选项
        const projectSelect = form.querySelector('#task-project');
        if (projectSelect) {
            projectSelect.innerHTML = this.projects.map(project => 
                `<option value="${project.id}">${project.name}</option>`
            ).join('');
        }
        
        modal.style.display = 'flex';
    }

    /**
     * 显示编辑任务模态框
     * @param {Object} task - 任务对象
     */
    showEditTaskModal(task) {
        const modal = document.getElementById('task-modal');
        const form = document.getElementById('task-form');
        const title = document.getElementById('task-modal-title');
        
        if (!modal || !form || !title) return;
        
        title.textContent = '编辑任务';
        form.dataset.mode = 'edit';
        form.dataset.taskId = task.id;
        
        // 填充表单数据
        form.querySelector('#task-name').value = task.name || '';
        form.querySelector('#task-description').value = task.description || '';
        form.querySelector('#task-project').value = task.project_id || '';
        form.querySelector('#task-config').value = JSON.stringify(task.config || {}, null, 2);
        
        modal.style.display = 'flex';
    }

    /**
     * 显示任务详情模态框
     * @param {Object} task - 任务对象
     */
    showTaskDetailModal(task) {
        const modal = document.getElementById('task-detail-modal');
        const content = document.getElementById('task-detail-content');
        
        if (!modal || !content) return;
        
        const project = this.projects.find(p => p.id === task.project_id);
        
        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">任务名称</label>
                        <div class="text-gray-900">${task.name}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">状态</label>
                        <div>${this.getStatusBadge(task.status)}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">所属项目</label>
                        <div class="text-gray-900">${project ? project.name : '未知项目'}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">创建时间</label>
                        <div class="text-gray-900">${helpers.formatDate(task.created_at)}</div>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">任务描述</label>
                    <div class="text-gray-900 whitespace-pre-wrap">${task.description || '无描述'}</div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">配置信息</label>
                    <div class="code-block">
                        <code>${JSON.stringify(task.config || {}, null, 2)}</code>
                    </div>
                </div>
                
                ${task.result ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">执行结果</label>
                        <div class="code-block">
                            <code>${JSON.stringify(task.result, null, 2)}</code>
                        </div>
                    </div>
                ` : ''}
                
                ${task.error_message ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">错误信息</label>
                        <div class="alert alert-danger">
                            ${task.error_message}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        modal.style.display = 'flex';
        
        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 显示批量操作模态框
     */
    showBulkActionModal() {
        if (this.selectedTasks.size === 0) {
            this.showError('请先选择要操作的任务');
            return;
        }
        
        const modal = document.getElementById('bulk-action-modal');
        if (!modal) return;
        
        modal.style.display = 'flex';
    }

    /**
     * 执行批量操作
     * @param {string} action - 操作类型
     */
    async executeBulkAction(action) {
        if (this.selectedTasks.size === 0) {
            this.showError('请先选择要操作的任务');
            return;
        }
        
        const actionNames = {
            execute: '执行',
            cancel: '取消',
            delete: '删除'
        };
        
        const actionName = actionNames[action] || action;
        
        if (!confirm(`确定要${actionName}选中的 ${this.selectedTasks.size} 个任务吗？`)) {
            return;
        }
        
        try {
            const result = await api.bulkTaskAction({
                task_ids: Array.from(this.selectedTasks),
                action: action
            });
            
            if (result.success) {
                this.showSuccess(`批量${actionName}操作完成`);
                this.selectedTasks.clear();
                this.loadTasks();
                this.closeBulkActionModal();
            } else {
                this.showError(`批量${actionName}操作失败: ` + result.error);
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
        const modal = document.getElementById('bulk-action-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('tasks-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        console.error('任务管理错误:', message);
        // 这里可以集成到全局通知系统
        alert('错误: ' + message);
    }

    /**
     * 显示成功信息
     * @param {string} message - 成功信息
     */
    showSuccess(message) {
        console.log('任务管理成功:', message);
        // 这里可以集成到全局通知系统
        alert('成功: ' + message);
    }

    /**
     * 获取任务管理HTML模板
     * @returns {string} HTML模板
     */
    static getTemplate() {
        return `
            <div class="task-manager-container">
                <!-- 工具栏 -->
                <div class="card mb-6">
                    <div class="card-body">
                        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
                            <div class="flex flex-col sm:flex-row sm:items-center space-y-2 sm:space-y-0 sm:space-x-2 md:space-x-4">
                                <div class="search-box">
                                    <i data-lucide="search" class="search-icon"></i>
                                    <input type="text" id="task-search" class="search-input" placeholder="搜索任务...">
                                </div>
                                
                                <select id="status-filter" class="filter-select">
                                    <option value="">所有状态</option>
                                    <option value="pending">待执行</option>
                                    <option value="running">运行中</option>
                                    <option value="completed">已完成</option>
                                    <option value="failed">失败</option>
                                    <option value="cancelled">已取消</option>
                                </select>
                                
                                <select id="project-filter" class="filter-select">
                                    <option value="">所有项目</option>
                                </select>
                            </div>
                            
                            <div class="flex items-center space-x-3">
                                <button id="bulk-action-btn" class="btn btn-outline" disabled>
                                    批量操作 (0)
                                </button>
                                <button id="refresh-tasks" class="btn btn-outline">
                                    <i data-lucide="refresh-cw" class="w-4 h-4 mr-2"></i>
                                    刷新
                                </button>
                                <button id="create-task-btn" class="btn btn-primary">
                                    <i data-lucide="plus" class="w-4 h-4 mr-2"></i>
                                    创建任务
                                </button>
                            </div>
                        </div>
                        
                        <!-- 统计信息 -->
                        <div id="task-stats" class="mt-4 pt-4 border-t border-gray-200"></div>
                    </div>
                </div>
                
                <!-- 加载状态 -->
                <div id="tasks-loading" class="text-center py-8" style="display: none;">
                    <div class="loading-dots">
                        <span style="--i: 0"></span>
                        <span style="--i: 1"></span>
                        <span style="--i: 2"></span>
                    </div>
                    <div class="mt-2 text-gray-600">加载中...</div>
                </div>
                
                <!-- 任务列表 -->
                <div id="tasks-list"></div>
                
                <!-- 分页 -->
                <div id="tasks-pagination" class="mt-6"></div>
            </div>
        `;
    }
}

// 创建全局实例
const taskManager = new TaskManager();

// 导出到全局
window.taskManager = taskManager;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = taskManager;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return taskManager;
    });
}