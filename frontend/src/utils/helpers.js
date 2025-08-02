/**
 * 工具函数模块
 * 提供通用的辅助功能
 */

// ==================== 时间处理 ====================

/**
 * 格式化时间
 * @param {string|Date} date - 时间
 * @param {string} format - 格式
 * @returns {string} 格式化后的时间
 */
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    if (!date) return '-';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '-';
    
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * 获取相对时间
 * @param {string|Date} date - 时间
 * @returns {string} 相对时间描述
 */
function getRelativeTime(date) {
    if (!date) return '-';
    
    const now = new Date();
    const target = new Date(date);
    const diff = now - target;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    const months = Math.floor(days / 30);
    const years = Math.floor(days / 365);
    
    if (years > 0) return `${years}年前`;
    if (months > 0) return `${months}个月前`;
    if (days > 0) return `${days}天前`;
    if (hours > 0) return `${hours}小时前`;
    if (minutes > 0) return `${minutes}分钟前`;
    if (seconds > 0) return `${seconds}秒前`;
    
    return '刚刚';
}

/**
 * 格式化持续时间
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的持续时间
 */
function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0秒';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (hours > 0) parts.push(`${hours}小时`);
    if (minutes > 0) parts.push(`${minutes}分钟`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}秒`);
    
    return parts.join('');
}

// ==================== 数字处理 ====================

/**
 * 格式化数字
 * @param {number} num - 数字
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的数字
 */
function formatNumber(num, decimals = 0) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    
    return Number(num).toLocaleString('zh-CN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的文件大小
 */
function formatFileSize(bytes, decimals = 2) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}

/**
 * 格式化百分比
 * @param {number} value - 数值
 * @param {number} total - 总数
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的百分比
 */
function formatPercentage(value, total, decimals = 1) {
    if (!total || total === 0) return '0%';
    
    const percentage = (value / total) * 100;
    return `${percentage.toFixed(decimals)}%`;
}

// ==================== 字符串处理 ====================

/**
 * 截断文本
 * @param {string} text - 文本
 * @param {number} length - 最大长度
 * @param {string} suffix - 后缀
 * @returns {string} 截断后的文本
 */
function truncateText(text, length = 50, suffix = '...') {
    if (!text) return '';
    if (text.length <= length) return text;
    
    return text.substring(0, length) + suffix;
}

/**
 * 转换为驼峰命名
 * @param {string} str - 字符串
 * @returns {string} 驼峰命名字符串
 */
function toCamelCase(str) {
    return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
}

/**
 * 转换为短横线命名
 * @param {string} str - 字符串
 * @returns {string} 短横线命名字符串
 */
function toKebabCase(str) {
    return str.replace(/([A-Z])/g, '-$1').toLowerCase();
}

/**
 * 生成随机字符串
 * @param {number} length - 长度
 * @returns {string} 随机字符串
 */
function generateRandomString(length = 8) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

// ==================== 数组处理 ====================

/**
 * 数组去重
 * @param {Array} arr - 数组
 * @param {string} key - 去重键名（对象数组）
 * @returns {Array} 去重后的数组
 */
function uniqueArray(arr, key = null) {
    if (!Array.isArray(arr)) return [];
    
    if (key) {
        const seen = new Set();
        return arr.filter(item => {
            const value = item[key];
            if (seen.has(value)) {
                return false;
            }
            seen.add(value);
            return true;
        });
    }
    
    return [...new Set(arr)];
}

/**
 * 数组分组
 * @param {Array} arr - 数组
 * @param {string|Function} key - 分组键名或函数
 * @returns {Object} 分组后的对象
 */
function groupBy(arr, key) {
    if (!Array.isArray(arr)) return {};
    
    return arr.reduce((groups, item) => {
        const groupKey = typeof key === 'function' ? key(item) : item[key];
        if (!groups[groupKey]) {
            groups[groupKey] = [];
        }
        groups[groupKey].push(item);
        return groups;
    }, {});
}

/**
 * 数组排序
 * @param {Array} arr - 数组
 * @param {string} key - 排序键名
 * @param {string} order - 排序方向 (asc/desc)
 * @returns {Array} 排序后的数组
 */
function sortArray(arr, key, order = 'asc') {
    if (!Array.isArray(arr)) return [];
    
    return [...arr].sort((a, b) => {
        const aVal = a[key];
        const bVal = b[key];
        
        if (aVal < bVal) return order === 'asc' ? -1 : 1;
        if (aVal > bVal) return order === 'asc' ? 1 : -1;
        return 0;
    });
}

// ==================== 对象处理 ====================

/**
 * 深拷贝对象
 * @param {*} obj - 对象
 * @returns {*} 拷贝后的对象
 */
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
}

/**
 * 合并对象
 * @param {Object} target - 目标对象
 * @param {...Object} sources - 源对象
 * @returns {Object} 合并后的对象
 */
function mergeObjects(target, ...sources) {
    if (!target) target = {};
    
    sources.forEach(source => {
        if (source) {
            Object.keys(source).forEach(key => {
                if (source[key] !== null && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    target[key] = mergeObjects(target[key] || {}, source[key]);
                } else {
                    target[key] = source[key];
                }
            });
        }
    });
    
    return target;
}

/**
 * 获取嵌套属性值
 * @param {Object} obj - 对象
 * @param {string} path - 属性路径
 * @param {*} defaultValue - 默认值
 * @returns {*} 属性值
 */
function getNestedValue(obj, path, defaultValue = null) {
    if (!obj || !path) return defaultValue;
    
    const keys = path.split('.');
    let current = obj;
    
    for (const key of keys) {
        if (current === null || current === undefined || !(key in current)) {
            return defaultValue;
        }
        current = current[key];
    }
    
    return current;
}

/**
 * 设置嵌套属性值
 * @param {Object} obj - 对象
 * @param {string} path - 属性路径
 * @param {*} value - 属性值
 */
function setNestedValue(obj, path, value) {
    if (!obj || !path) return;
    
    const keys = path.split('.');
    let current = obj;
    
    for (let i = 0; i < keys.length - 1; i++) {
        const key = keys[i];
        if (!(key in current) || typeof current[key] !== 'object') {
            current[key] = {};
        }
        current = current[key];
    }
    
    current[keys[keys.length - 1]] = value;
}

// ==================== 验证函数 ====================

/**
 * 验证邮箱
 * @param {string} email - 邮箱地址
 * @returns {boolean} 是否有效
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * 验证URL
 * @param {string} url - URL地址
 * @returns {boolean} 是否有效
 */
function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

/**
 * 验证手机号
 * @param {string} phone - 手机号
 * @returns {boolean} 是否有效
 */
function isValidPhone(phone) {
    const phoneRegex = /^1[3-9]\d{9}$/;
    return phoneRegex.test(phone);
}

/**
 * 验证身份证号
 * @param {string} idCard - 身份证号
 * @returns {boolean} 是否有效
 */
function isValidIdCard(idCard) {
    const idCardRegex = /(^\d{15}$)|(^\d{18}$)|(^\d{17}(\d|X|x)$)/;
    return idCardRegex.test(idCard);
}

// ==================== DOM操作 ====================

/**
 * 获取元素
 * @param {string} selector - 选择器
 * @param {Element} context - 上下文元素
 * @returns {Element} 元素
 */
function $(selector, context = document) {
    return context.querySelector(selector);
}

/**
 * 获取所有元素
 * @param {string} selector - 选择器
 * @param {Element} context - 上下文元素
 * @returns {NodeList} 元素列表
 */
function $$(selector, context = document) {
    return context.querySelectorAll(selector);
}

/**
 * 添加类名
 * @param {Element} element - 元素
 * @param {string} className - 类名
 */
function addClass(element, className) {
    if (element && className) {
        element.classList.add(className);
    }
}

/**
 * 移除类名
 * @param {Element} element - 元素
 * @param {string} className - 类名
 */
function removeClass(element, className) {
    if (element && className) {
        element.classList.remove(className);
    }
}

/**
 * 切换类名
 * @param {Element} element - 元素
 * @param {string} className - 类名
 */
function toggleClass(element, className) {
    if (element && className) {
        element.classList.toggle(className);
    }
}

/**
 * 检查是否包含类名
 * @param {Element} element - 元素
 * @param {string} className - 类名
 * @returns {boolean} 是否包含
 */
function hasClass(element, className) {
    return element && className && element.classList.contains(className);
}

// ==================== 事件处理 ====================

/**
 * 添加事件监听器
 * @param {Element} element - 元素
 * @param {string} event - 事件名
 * @param {Function} handler - 处理函数
 * @param {Object} options - 选项
 */
function on(element, event, handler, options = {}) {
    if (element && event && handler) {
        element.addEventListener(event, handler, options);
    }
}

/**
 * 移除事件监听器
 * @param {Element} element - 元素
 * @param {string} event - 事件名
 * @param {Function} handler - 处理函数
 */
function off(element, event, handler) {
    if (element && event && handler) {
        element.removeEventListener(event, handler);
    }
}

/**
 * 触发事件
 * @param {Element} element - 元素
 * @param {string} event - 事件名
 * @param {Object} detail - 事件详情
 */
function trigger(element, event, detail = {}) {
    if (element && event) {
        const customEvent = new CustomEvent(event, { detail });
        element.dispatchEvent(customEvent);
    }
}

// ==================== 存储操作 ====================

/**
 * 本地存储
 */
const storage = {
    /**
     * 设置本地存储
     * @param {string} key - 键名
     * @param {*} value - 值
     */
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('设置本地存储失败:', error);
        }
    },
    
    /**
     * 获取本地存储
     * @param {string} key - 键名
     * @param {*} defaultValue - 默认值
     * @returns {*} 存储值
     */
    get(key, defaultValue = null) {
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : defaultValue;
        } catch (error) {
            console.error('获取本地存储失败:', error);
            return defaultValue;
        }
    },
    
    /**
     * 移除本地存储
     * @param {string} key - 键名
     */
    remove(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error('移除本地存储失败:', error);
        }
    },
    
    /**
     * 清空本地存储
     */
    clear() {
        try {
            localStorage.clear();
        } catch (error) {
            console.error('清空本地存储失败:', error);
        }
    }
};

// ==================== 工具函数 ====================

/**
 * 防抖函数
 * @param {Function} func - 函数
 * @param {number} wait - 等待时间
 * @param {boolean} immediate - 是否立即执行
 * @returns {Function} 防抖后的函数
 */
function debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

/**
 * 节流函数
 * @param {Function} func - 函数
 * @param {number} limit - 限制时间
 * @returns {Function} 节流后的函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 延迟执行
 * @param {number} ms - 延迟时间（毫秒）
 * @returns {Promise} Promise对象
 */
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 重试函数
 * @param {Function} fn - 要重试的函数
 * @param {number} retries - 重试次数
 * @param {number} delay - 延迟时间
 * @returns {Promise} Promise对象
 */
async function retry(fn, retries = 3, delayMs = 1000) {
    try {
        return await fn();
    } catch (error) {
        if (retries > 0) {
            await delay(delayMs);
            return retry(fn, retries - 1, delayMs);
        }
        throw error;
    }
}

/**
 * 复制到剪贴板
 * @param {string} text - 要复制的文本
 * @returns {Promise} Promise对象
 */
async function copyToClipboard(text) {
    try {
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(text);
        } else {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
        }
        return true;
    } catch (error) {
        console.error('复制失败:', error);
        return false;
    }
}

/**
 * 下载文件
 * @param {string} url - 文件URL
 * @param {string} filename - 文件名
 */
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * 获取URL参数
 * @param {string} name - 参数名
 * @param {string} url - URL地址
 * @returns {string} 参数值
 */
function getUrlParam(name, url = window.location.href) {
    const urlObj = new URL(url);
    return urlObj.searchParams.get(name);
}

/**
 * 设置URL参数
 * @param {string} name - 参数名
 * @param {string} value - 参数值
 * @param {boolean} replace - 是否替换历史记录
 */
function setUrlParam(name, value, replace = false) {
    const url = new URL(window.location.href);
    url.searchParams.set(name, value);
    
    if (replace) {
        window.history.replaceState({}, '', url.toString());
    } else {
        window.history.pushState({}, '', url.toString());
    }
}

// ==================== 导出函数 ====================

// 将所有函数添加到全局对象
const helpers = {
    // 时间处理
    formatDate,
    getRelativeTime,
    formatDuration,
    
    // 数字处理
    formatNumber,
    formatFileSize,
    formatPercentage,
    
    // 字符串处理
    truncateText,
    toCamelCase,
    toKebabCase,
    generateRandomString,
    
    // 数组处理
    uniqueArray,
    groupBy,
    sortArray,
    
    // 对象处理
    deepClone,
    mergeObjects,
    getNestedValue,
    setNestedValue,
    
    // 验证函数
    isValidEmail,
    isValidUrl,
    isValidPhone,
    isValidIdCard,
    
    // DOM操作
    $,
    $$,
    addClass,
    removeClass,
    toggleClass,
    hasClass,
    
    // 事件处理
    on,
    off,
    trigger,
    
    // 存储操作
    storage,
    
    // 工具函数
    debounce,
    throttle,
    delay,
    retry,
    copyToClipboard,
    downloadFile,
    getUrlParam,
    setUrlParam
};

// 导出到全局
window.helpers = helpers;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = helpers;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return helpers;
    });
}