#!/bin/bash

# ============================================
# 脚本名称：init_git_repo.sh
# 功能：在当前或指定目录初始化 Git 仓库，
#       自动生成 SSH 密钥并配置 GitHub 远程连接
# ============================================

set -e  # 遇到错误立即退出

# ---------- 颜色定义 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------- 辅助函数 ----------
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------- 检查依赖 ----------
check_dependencies() {
    info "检查依赖..."
    
    #if ! command -v git &>/dev/null; then
    #    error "未找到 Git，请先安装：sudo apt install git"
    #    exit 1
    #fi
    
    if ! command -v ssh-keygen &>/dev/null; then
        warn "未找到 ssh-keygen，尝试安装 openssh-client..."
        sudo apt update && sudo apt install -y openssh-client
    fi
    
    success "所有依赖检查通过"
}

# ---------- 获取用户输入 ----------
get_user_input() {
    echo ""
    echo "==================== Git 仓库初始化 ===================="
    
    # 工作目录路径
    read -p "请输入项目目录路径（默认为当前目录）: " WORK_DIR
    WORK_DIR="${WORK_DIR:-$(pwd)}"
    
    # GitHub 用户名
    read -p "请输入你的 GitHub 用户名: " GITHUB_USER
    while [[ -z "$GITHUB_USER" ]]; do
        warn "GitHub 用户名不能为空！"
        read -p "请输入你的 GitHub 用户名: " GITHUB_USER
    done
    
    # GitHub 邮箱
    read -p "请输入你的 GitHub 注册邮箱: " GIT_EMAIL
    while [[ -z "$GIT_EMAIL" ]]; do
        warn "邮箱不能为空！"
        read -p "请输入你的 GitHub 注册邮箱: " GIT_EMAIL
    done
    
    # 仓库名称
    read -p "请输入 GitHub 仓库名称（默认使用目录名）: " REPO_NAME
    REPO_NAME="${REPO_NAME:-$(basename "$WORK_DIR")}"
    
    # SSH 密钥文件名
    read -p "请输入 SSH 密钥文件名（默认为 id_ed25519_github）: " KEY_NAME
    KEY_NAME="${KEY_NAME:-id_ed25519_github}"
    
    echo "=========================================================="
    echo ""
}

# ---------- 初始化 Git 仓库 ----------
init_git_repo() {
    info "初始化 Git 仓库..."
    
    # 创建目录（如果不存在）
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    
    # 如果已有 .git 目录，询问是否重新初始化
    if [ -d ".git" ]; then
        warn "该目录已经是一个 Git 仓库！"
        read -p "是否重新初始化？(y/N): " REINIT
        if [[ "$REINIT" =~ ^[Yy]$ ]]; then
            rm -rf .git
            git init
        else
            info "使用现有 Git 仓库"
        fi
    else
        git init
    fi
    
    success "Git 仓库初始化完成"
}

# ---------- 配置 Git 用户信息 ----------
configure_git() {
    info "配置 Git 用户信息..."
    
    git config user.name "$GITHUB_USER"
    git config user.email "$GIT_EMAIL"
    
    # 可选：设置默认分支为 main
    git checkout -b main 2>/dev/null || git branch -M main
    
    success "Git 用户信息配置完成"
}

# ---------- 生成 SSH 密钥 ----------
generate_ssh_key() {
    local SSH_KEY_PATH="$HOME/.ssh/$KEY_NAME"
    
    # 检查是否已存在该密钥
    if [ -f "$SSH_KEY_PATH" ]; then
        warn "SSH 密钥已存在：$SSH_KEY_PATH"
        read -p "是否覆盖？(y/N): " OVERWRITE
        if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
            info "使用现有密钥"
            return
        fi
    fi
    
    info "生成新的 SSH 密钥..."
    
    # 确保 .ssh 目录存在且权限正确
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    
    # 生成 Ed25519 密钥（更安全高效）
    ssh-keygen -t ed25519 -C "$GIT_EMAIL" -f "$SSH_KEY_PATH" -N ""
    
    # 添加私钥到 ssh-agent
    eval "$(ssh-agent -s)" >/dev/null 2>&1
    ssh-add "$SSH_KEY_PATH" 2>/dev/null || {
        warn "无法自动添加密钥到 ssh-agent，请手动运行：ssh-add $SSH_KEY_PATH"
    }
    
    success "SSH 密钥生成成功：$SSH_KEY_PATH.pub"
    
    # 显示公钥内容
    echo ""
    echo "==================== 公钥内容（请添加到 GitHub） ===================="
    cat "${SSH_KEY_PATH}.pub"
    echo "===================================================================="
    echo ""
}

# ---------- 配置 SSH Config ----------
configure_ssh_config() {
    local SSH_CONFIG="$HOME/.ssh/config"
    local HOST_ALIAS="github.com-$KEY_NAME"
    
    info "配置 SSH Config..."
    
    # 备份原配置文件
    if [ -f "$SSH_CONFIG" ] && [ ! -f "${SSH_CONFIG}.bak" ]; then
        cp "$SSH_CONFIG" "${SSH_CONFIG}.bak"
        info "已备份原 SSH 配置到 ${SSH_CONFIG}.bak"
    fi
    
    # 检查是否已存在相同配置
    if grep -q "Host github.com-$KEY_NAME" "$SSH_CONFIG" 2>/dev/null; then
        warn "SSH Config 中已存在该主机配置"
        return
    fi
    
    # 追加配置
    cat >> "$SSH_CONFIG" << EOF

# GitHub - $KEY_NAME ($(date '+%Y-%m-%d'))
Host $HOST_ALIAS
    HostName github.com
    User git
    IdentityFile ~/.ssh/$KEY_NAME
    IdentitiesOnly yes
EOF
    
    chmod 600 "$SSH_CONFIG"
    success "SSH Config 配置完成"
}

# ---------- 测试 SSH 连接 ----------
test_ssh_connection() {
    info "测试 SSH 连接..."
    
    # 使用新配置测试连接
    local TEST_OUTPUT
    TEST_OUTPUT=$(ssh -T -o StrictHostKeyChecking=accept-new "git@github.com" 2>&1) || true
    
    if echo "$TEST_OUTPUT" | grep -q "successfully authenticated"; then
        success "SSH 连接测试成功！"
    else
        warn "SSH 连接测试结果：$TEST_OUTPUT"
        warn "请确保已将公钥添加到 GitHub 账户设置中"
        echo ""
        echo "操作步骤："
        echo "1. 登录 GitHub → Settings → SSH and GPG keys"
        echo "2. 点击 New SSH key"
        echo "3. 将上面显示的公钥内容粘贴进去并保存"
        echo ""
        read -p "添加完成后按回车继续..." 
    fi
}

# ---------- 添加远程仓库 ----------
add_remote() {
    local REMOTE_URL="git@github.com:$GITHUB_USER/$REPO_NAME.git"
    
    info "添加远程仓库..."
    
    # 检查是否已有远程仓库
    if git remote get-url origin &>/dev/null; then
        warn "远程仓库 'origin' 已存在：$(git remote get-url origin)"
        read -p "是否覆盖？(y/N): " OVERWRITE_REMOTE
        if [[ "$OVERWRITE_REMOTE" =~ ^[Yy]$ ]]; then
            git remote set-url origin "$REMOTE_URL"
        else
            info "保留现有远程仓库配置"
            return
        fi
    else
        git remote add origin "$REMOTE_URL"
    fi
    
    success "远程仓库配置完成：$REMOTE_URL"
}

# ---------- 创建初始提交 ----------
create_initial_commit() {
    info "创建初始提交..."
    
    # 检查是否有文件需要提交
    if [ -z "$(ls -A .)" ]; then
        warn "目录为空，创建一个 README.md 作为初始文件"
        echo "# $REPO_NAME" > README.md
        echo "" >> README.md
        echo "项目描述：" >> README.md
    fi
    
    # 创建 .gitignore（如果不存在）
    if [ ! -f ".gitignore" ]; then
        cat > .gitignore << 'EOF'
# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Python
__pycache__/
*.py[cod]
*.so
.env

# Node
node_modules/
npm-debug.log*
EOF
        info "已创建默认 .gitignore 文件"
    fi
    
    git add .
    git commit -m "Initial commit" 2>/dev/null || warn "没有文件需要提交"
    
    success "初始提交完成"
}

# ---------- 推送至 GitHub ----------
push_to_github() {
    info "推送到 GitHub..."
    
    # 检查是否已登录 GitHub（通过 SSH）
    if ssh -T -o StrictHostKeyChecking=no "git@github.com" 2>&1 | grep -q "successfully authenticated"; then
        git push -u origin main 2>&1 || {
            warn "推送失败，可能原因："
            warn "1. GitHub 上还没有创建仓库 '$REPO_NAME'"
            warn "2. SSH 密钥未正确配置"
            echo ""
            echo "请在 GitHub 上创建仓库后再手动推送："
            echo "  git push -u origin main"
        }
        success "推送成功！"
    else
        warn "跳过推送，请手动执行：git push -u origin main"
    fi
}

# ---------- 主流程 ----------
main() {
    echo ""
    echo "========================================"
    echo "   Git 仓库初始化脚本 (GitHub SSH)"
    echo "========================================"
    echo ""
    
    check_dependencies
    get_user_input
    init_git_repo
    configure_git
    generate_ssh_key
    configure_ssh_config
    test_ssh_connection
    add_remote
    create_initial_commit
    push_to_github
    
    echo ""
    echo "========================================"
    success "全部完成！"
    echo "项目目录：$WORK_DIR"
    echo "远程仓库：git@github.com:$GITHUB_USER/$REPO_NAME.git"
    echo "SSH 密钥：~/.ssh/$KEY_NAME"
    echo ""
    echo "后续操作："
    echo "  cd $WORK_DIR"
    echo "  git add <文件>"
    echo "  git commit -m \"提交说明\""
    echo "  git push"
    echo "========================================"
}

# ---------- 执行主函数 ----------
main "$@"