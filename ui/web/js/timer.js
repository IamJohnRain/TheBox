/**
 * @fileoverview 倒计时模块。
 *
 * 管理审讯倒计时的显示，包括时间格式化、
 * 30秒以下变红闪烁效果。
 *
 * @author The Box Dev Team
 */

/**
 * TimerManager - 倒计时管理类。
 *
 * 负责：
 * - 更新倒计时显示（格式 MM:SS）
 * - 30 秒以下切换为危险红色闪烁
 * - 60 秒以下切换为警告黄色
 * - 清空倒计时显示
 */
class TimerManager {
    /**
     * 创建 TimerManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 倒计时显示元素 */
        this.display = document.getElementById('timer-display');

        /** @type {number|null} 危险闪烁动画定时器 */
        this._dangerInterval = null;

        /** @type {number|null} 上次剩余秒数，用于模态框关闭后恢复渲染 */
        this._lastTimeLeft = null;
    }

    /**
     * 更新倒计时显示。
     *
     * @param {number} timeLeft - 剩余秒数
     * @returns {void}
     *
     * @example
     * timerManager.update(300);  // 显示 "05:00"
     * timerManager.update(45);   // 显示 "00:45"，黄色警告
     * timerManager.update(15);   // 显示 "00:15"，红色闪烁
     */
    update(timeLeft) {
        this._lastTimeLeft = timeLeft;
        // 模态框可见时暂停 UI 更新，减少重绘
        if (window.modalManager && window.modalManager.isVisible()) return;
        this._render(timeLeft);
    }

    /**
     * 渲染倒计时显示到 DOM。
     *
     * @param {number} timeLeft - 剩余秒数
     * @returns {void}
     */
    _render(timeLeft) {
        if (!this.display) {
            console.error('[TimerManager] Display element not found');
            return;
        }

        if (timeLeft === null || timeLeft === undefined || isNaN(timeLeft)) {
            this.clear();
            return;
        }

        // 格式化为 MM:SS
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        this.display.textContent =
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

        // 更新样式类
        this.display.className = 'timer-display';

        if (timeLeft <= 30) {
            this.display.classList.add('danger');
        } else if (timeLeft <= 60) {
            this.display.classList.add('warning');
        }
    }

    /**
     * 恢复因模态框暂停的计时器 UI 更新。
     * 在模态框关闭后调用，将最新计时数据渲染到 DOM。
     *
     * @returns {void}
     */
    flush() {
        if (this._lastTimeLeft !== null) {
            this._render(this._lastTimeLeft);
        }
    }

    /**
     * 清空倒计时显示，恢复初始状态。
     */
    clear() {
        if (this.display) {
            this.display.textContent = '--';
            this.display.className = 'timer-display';
        }
    }
}
