/**
 * @fileoverview 键盘快捷键管理模块。
 *
 * 提供全局键盘快捷键的注册、注销、启用/禁用管理。
 * 支持组合键（如 Ctrl+S、Ctrl+Shift+P）和单键（如 Escape）。
 * 自动忽略输入框内的冲突快捷键，避免干扰正常输入。
 *
 * @author The Box Dev Team
 */

/**
 * 键盘快捷键管理器。
 *
 * 监听 document 级别的 keydown 事件，根据注册的绑定执行回调。
 * 快捷键标识格式：修饰键 + 主键，用 `+` 连接，全部小写。
 * 例如：'ctrl+s', 'ctrl+shift+p', 'escape', 'enter'。
 *
 * @example
 * const km = new KeyboardManager();
 * km.register('ctrl+s', () => saveDocument());
 * km.register('escape', () => closeModal());
 * km.setEnabled(false); // 临时禁用
 */
class KeyboardManager {
    /**
     * 创建 KeyboardManager 实例。
     * 构造时立即注册全局 keydown 监听器。
     */
    constructor() {
        /** @private @type {Map<string, Function>} 快捷键标识 → 回调映射 */
        this._bindings = new Map();

        /** @private @type {boolean} 是否启用快捷键响应 */
        this._enabled = true;

        this._setupGlobalListener();
    }

    /**
     * 设置全局键盘监听器。
     *
     * 仅在 document 上注册一个 keydown 监听器，通过查找 _bindings Map
     * 来分发事件，避免多次 addEventListener 带来的性能开销。
     *
     * @private
     */
    _setupGlobalListener() {
        document.addEventListener('keydown', (e) => {
            if (!this._enabled) return;

            // 构建快捷键标识
            const key = this._buildKeyIdentifier(e);

            // 检查是否有匹配的绑定
            if (this._bindings.has(key)) {
                e.preventDefault();
                e.stopPropagation();
                this._bindings.get(key)();
            }
        });
    }

    /**
     * 根据键盘事件构建快捷键标识。
     *
     * 修饰键按固定顺序排列（ctrl → shift → alt），主键始终在最后。
     * 主键统一转为小写，确保大小写不敏感匹配。
     *
     * @param {KeyboardEvent} e - 原生键盘事件
     * @returns {string} 快捷键标识，如 'ctrl+s', 'escape', 'ctrl+shift+p'
     * @private
     */
    _buildKeyIdentifier(e) {
        const parts = [];
        if (e.ctrlKey || e.metaKey) parts.push('ctrl');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');
        parts.push(e.key.toLowerCase());
        return parts.join('+');
    }

    /**
     * 注册快捷键。
     *
     * 如果该快捷键标识已存在，将覆盖旧回调。
     * 标识会被自动转为小写，因此 'Ctrl+S' 和 'ctrl+s' 等效。
     *
     * @param {string} key - 快捷键标识，如 'ctrl+s', 'enter', 'escape'
     * @param {Function} callback - 按下快捷键时执行的回调函数
     * @throws {TypeError} 当 key 不是字符串或 callback 不是函数时
     */
    register(key, callback) {
        if (typeof key !== 'string') {
            throw new TypeError('[KeyboardManager] key must be a string');
        }
        if (typeof callback !== 'function') {
            throw new TypeError('[KeyboardManager] callback must be a function');
        }
        this._bindings.set(key.toLowerCase(), callback);
    }

    /**
     * 注销快捷键。
     *
     * 如果该快捷键标识不存在，操作会被静默忽略。
     *
     * @param {string} key - 要注销的快捷键标识
     */
    unregister(key) {
        this._bindings.delete(key.toLowerCase());
    }

    /**
     * 启用或禁用快捷键响应。
     *
     * 禁用后所有已注册的快捷键都不会触发回调，
     * 但输入框自身的键盘事件不受影响（因为输入框事件不经过 KeyboardManager）。
     *
     * @param {boolean} enabled - true 启用，false 禁用
     */
    setEnabled(enabled) {
        this._enabled = Boolean(enabled);
    }

    /**
     * 查询快捷键是否启用。
     *
     * @returns {boolean} 当前启用状态
     */
    isEnabled() {
        return this._enabled;
    }

    /**
     * 检查指定快捷键是否已注册。
     *
     * @param {string} key - 快捷键标识
     * @returns {boolean} 是否已注册
     */
    has(key) {
        return this._bindings.has(key.toLowerCase());
    }

    /**
     * 清除所有已注册的快捷键绑定。
     */
    clear() {
        this._bindings.clear();
    }
}
