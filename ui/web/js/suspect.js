/**
 * @fileoverview 嫌疑人模块。
 *
 * 管理嫌疑人列表加载、当前嫌疑人信息更新、嫌疑人切换，
 * 以及压力条和状态徽章的显示更新。
 *
 * @author The Box Dev Team
 */

/**
 * SuspectManager - 嫌疑人管理类。
 *
 * 负责：
 * - 加载嫌疑人列表到下拉选择器
 * - 更新当前选中嫌疑人的信息（名称、角色、压力值等）
 * - 切换嫌疑人选择
 * - 压力条动态更新（低/中/高三档配色）
 * - 状态徽章更新
 */
class SuspectManager {
    /**
     * 创建 SuspectManager 实例。
     */
    constructor() {
        /** @type {HTMLSelectElement} 嫌疑人选择器 */
        this.selector = document.getElementById('suspect-selector');

        /** @type {HTMLElement} 嫌疑人头像占位符 */
        this.avatar = document.getElementById('suspect-avatar');

        /** @type {HTMLElement} 嫌疑人名称 */
        this.nameEl = document.getElementById('suspect-name');

        /** @type {HTMLElement} 嫌疑人角色 */
        this.roleEl = document.getElementById('suspect-role');

        /** @type {HTMLElement} 状态徽章 */
        this.statusBadge = document.getElementById('suspect-status');

        /** @type {HTMLElement} 压力条 */
        this.pressureBar = document.getElementById('pressure-bar');

        /** @type {HTMLElement} 压力值文本 */
        this.pressureValue = document.getElementById('pressure-value');

        /** @type {HTMLButtonElement} 施压按钮 */
        this.btnPressure = document.getElementById('btn-pressure');

        /** @type {HTMLButtonElement} 共情按钮 */
        this.btnEmpathy = document.getElementById('btn-empathy');

        /** @type {Array.<{name: string, role: string, pressure: number}>} 嫌疑人列表缓存 */
        this.suspects = [];

        /** @type {number} 当前选中嫌疑人索引 */
        this.currentIndex = -1;
    }

    /**
     * 加载嫌疑人列表到选择器。
     *
     * @param {Array.<{name: string, role: string, pressure: number}>} suspects - 嫌疑人数据数组
     * @returns {void}
     *
     * @example
     * suspectManager.loadSuspects([
     *     { name: '张三', role: '项目经理', pressure: 0 },
     *     { name: '李四', role: '会计', pressure: 30 },
     *     { name: '王五', role: '保安', pressure: 60 }
     * ]);
     */
    loadSuspects(suspects) {
        this.suspects = suspects || [];
        if (!this.selector) {
            console.error('[SuspectManager] Selector element not found');
            return;
        }

        // 清空并重建选项
        this.selector.innerHTML = '<option value="">选择嫌疑人...</option>';

        this.suspects.forEach((suspect, index) => {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = suspect.name || `嫌疑人 ${index + 1}`;
            this.selector.appendChild(option);
        });

        // 重置当前状态
        this.currentIndex = -1;
        this._resetDisplay();
    }

    /**
     * 更新当前嫌疑人的压力值。
     *
     * @param {string} name - 嫌疑人名称
     * @param {number} pressure - 压力值（0-100）
     * @returns {void}
     */
    updateSuspect(name, pressure) {
        // 更新名称显示
        if (name && this.nameEl) {
            this.nameEl.textContent = name;
        }

        // 更新头像占位符为姓名首字
        if (name && this.avatar) {
            this.avatar.textContent = name.charAt(0);
        }

        // 更新压力条
        this._updatePressure(pressure);

        // 更新状态徽章
        this._updateStatusBadge(pressure);

        // 同步 suspects 列表中的数据
        if (this.currentIndex >= 0 && this.suspects[this.currentIndex]) {
            this.suspects[this.currentIndex].name = name;
            this.suspects[this.currentIndex].pressure = pressure;
        }
    }

    /**
     * 切换选中的嫌疑人。
     *
     * @param {number} index - 嫌疑人索引
     * @returns {void}
     */
    selectSuspect(index) {
        if (index < 0 || index >= this.suspects.length) {
            console.warn('[SuspectManager] Invalid suspect index:', index);
            return;
        }

        this.currentIndex = index;

        // 更新选择器
        if (this.selector) {
            this.selector.value = String(index);
        }

        const suspect = this.suspects[index];

        // 更新显示
        if (suspect) {
            if (suspect.name && this.nameEl) {
                this.nameEl.textContent = suspect.name;
            }
            if (suspect.name && this.avatar) {
                this.avatar.textContent = suspect.name.charAt(0);
            }
            if (suspect.role && this.roleEl) {
                this.roleEl.textContent = suspect.role;
            }
            this._updatePressure(suspect.pressure || 0);
            this._updateStatusBadge(suspect.pressure || 0);
        }

        // 启用操作按钮
        this._setActionButtonsEnabled(true);
    }

    /**
     * 清空嫌疑人面板，恢复初始状态。
     */
    clear() {
        this.suspects = [];
        this.currentIndex = -1;

        if (this.selector) {
            this.selector.innerHTML = '<option value="">选择嫌疑人...</option>';
        }

        this._resetDisplay();
    }

    /**
     * 启用或禁用操作按钮。
     *
     * @param {boolean} enabled - true 启用，false 禁用
     */
    setActionButtonsEnabled(enabled) {
        this._setActionButtonsEnabled(enabled);
    }

    /**
     * 重置面板显示到初始状态。
     * @private
     */
    _resetDisplay() {
        if (this.nameEl) this.nameEl.textContent = '未选择';
        if (this.roleEl) this.roleEl.textContent = '--';
        if (this.avatar) this.avatar.textContent = '?';
        this._updatePressure(0);
        this._updateStatusBadge(0);
        this._setActionButtonsEnabled(false);
    }

    /**
     * 更新压力条显示。
     * @private
     * @param {number} pressure - 压力值（0-100）
     */
    _updatePressure(pressure) {
        const percentage = Math.min(100, Math.max(0, pressure));

        if (this.pressureBar) {
            this.pressureBar.style.width = percentage + '%';
            this.pressureBar.className = 'pressure-bar ' + this._getPressureClass(percentage);
        }

        if (this.pressureValue) {
            this.pressureValue.textContent = percentage + '%';
            this.pressureValue.className = 'pressure-value ' + this._getPressureClass(percentage);
        }
    }

    /**
     * 根据压力值获取 CSS 类名。
     * @private
     * @param {number} percentage - 压力百分比
     * @returns {string} CSS 类名：'low' / 'medium' / 'high'
     */
    _getPressureClass(percentage) {
        if (percentage < 30) return 'low';
        if (percentage < 70) return 'medium';
        return 'high';
    }

    /**
     * 更新状态徽章。
     * @private
     * @param {number} pressure - 压力值
     */
    _updateStatusBadge(pressure) {
        if (!this.statusBadge) return;

        if (pressure >= 80) {
            this.statusBadge.textContent = '崩溃';
            this.statusBadge.className = 'suspect-status-badge broken';
        } else if (pressure >= 30) {
            this.statusBadge.textContent = '审讯中';
            this.statusBadge.className = 'suspect-status-badge interrogating';
        } else if (this.currentIndex >= 0) {
            this.statusBadge.textContent = '就绪';
            this.statusBadge.className = 'suspect-status-badge ready';
        } else {
            this.statusBadge.textContent = '就绪';
            this.statusBadge.className = 'suspect-status-badge ready';
        }
    }

    /**
     * 启用或禁用施压/共情按钮。
     * @private
     * @param {boolean} enabled - true 启用，false 禁用
     */
    _setActionButtonsEnabled(enabled) {
        if (this.btnPressure) this.btnPressure.disabled = !enabled;
        if (this.btnEmpathy) this.btnEmpathy.disabled = !enabled;
    }
}
