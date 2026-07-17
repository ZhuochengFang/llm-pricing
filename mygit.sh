#!/bin/sh

# ============================================
# 半自动 Git 初始化 + SSH 推送脚本
# 兼容 dash 和 bash
# 使用方法：
#   1. 将脚本放到项目根目录
#   2. chmod +x init_git.sh
#   3. ./init_git.sh
# ============================================

set -e  # 遇到错误立即退出

# 颜色定义（dash 也支持）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出函数
info() {
    printf "${GREEN}[INFO]${NC} %s\n" "$1"
}

warn() {
    printf "${YELLOW}[WARN]${NC} %s\n" "$1"
}

error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1"
    exit 1
}

# 检查 Git 是否安装
check_git() {
    if ! command -v git >/dev/null 2>&1; then
        error "Git 未安装！请先安装 Git：sudo apt install git 或 brew install git"
    fi
    info "Git 版本：$(git --version)"
}

# 检查当前目录是否已经是 Git 仓库
check_existing_repo() {
    if [ -d ".git" ]; then
        warn "当前目录已是 Git 仓库 (.git 目录存在)"
        printf "是否重新初始化？(y/N): "
        read -r answer
        case "$answer" in
            [yY]|[yY][eE][sS])
                rm -rf .git
                info "已删除旧的 .git 目录"
                ;;
            *)
                info "退出脚本，保持现有仓库"
                exit 0
                ;;
        esac
    fi
}

# 获取用户输入
get_user_input() {
    # 获取 GitHub 用户名
    printf "请输入你的 GitHub 用户名: "
    read -r github_user
    while [ -z "$github_user" ]; do
        warn "用户名不能为空"
        printf "请输入你的 GitHub 用户名: "
        read -r github_user
    done

    # 获取仓库名称（默认使用当前目录名）
    default_repo=$(basename "$(pwd)")
    printf "请输入 GitHub 仓库名称 (默认: %s): " "$default_repo"
    read -r repo_name
    repo_name="${repo_name:-$default_repo}"

    # 获取默认分支名称（GitHub 现在默认 main）
    printf "请输入主分支名称 (默认: main): "
    read -r branch_name
    branch_name="${branch_name:-main}"
}

# 检查 SSH 连接
check_ssh() {
    info "正在测试 SSH 连接到 GitHub..."
    if ssh -T git@github.com 2>&1 | grep -q "successfully"; then
        info "SSH 连接测试通过！"
    else
        warn "SSH 连接测试未完全通过，但可能是正常现象（首次连接需要确认）"
        warn "如果后续推送失败，请检查 SSH 密钥配置"
        printf "是否继续？(Y/n): "
        read -r continue_choice
        case "$continue_choice" in
            [nN]|[nN][oO])
                error "请先配置 SSH 密钥后再运行此脚本"
                ;;
            *)
                info "继续执行..."
                ;;
        esac
    fi
}

# 初始化 Git 仓库
init_repo() {
    info "正在初始化 Git 仓库..."
    git init -b "$branch_name" || git init && git checkout -b "$branch_name"
    info "Git 仓库初始化完成，默认分支: $branch_name"
}

# 创建 .gitignore（如果不存在）
create_gitignore() {
    if [ ! -f ".gitignore" ]; then
        printf "是否创建 .gitignore 文件？(y/N): "
        read -r create_gi
        case "$create_gi" in
            [yY]|[yY][eE][sS])
                cat > .gitignore << 'EOF'
# 操作系统文件
.DS_Store
Thumbs.db
*.swp
*.swo

# IDE 配置文件
.idea/
.vscode/
*.suo
*.ntvs*
*.user
*.userosscache
*.sln.docstates

# 依赖目录
node_modules/
vendor/
bower_components/

# 编译输出
dist/
build/
*.o
*.pyc
__pycache__/

# 环境变量文件
.env
.env.local

# 日志文件
*.log
npm-debug.log*

# 包锁定文件（可选）
package-lock.json
yarn.lock
EOF
                info ".gitignore 文件已创建"
                ;;
            *)
                info "跳过创建 .gitignore"
                ;;
        esac
    else
        info ".gitignore 文件已存在，跳过创建"
    fi
}

# 添加并提交文件
add_and_commit() {
    info "正在添加文件到暂存区..."
    git add .

    # 检查是否有文件被添加
    if git diff --cached --quiet; then
        warn "没有文件被添加到暂存区（所有文件可能已被忽略）"
        printf "是否强制添加所有文件？(y/N): "
        read -r force_add
        case "$force_add" in
            [yY]|[yY][eE][sS])
                git add -f .
                ;;
            *)
                error "没有文件可提交，请手动添加文件后重试"
                ;;
        esac
    fi

    # 提交
    printf "请输入提交信息 (默认: Initial commit): "
    read -r commit_msg
    commit_msg="${commit_msg:-Initial commit}"
    
    git commit -m "$commit_msg"
    info "文件已提交到本地仓库"
}

# 关联远程仓库并推送
push_to_remote() {
    local remote_url="git@github.com:${github_user}/${repo_name}.git"
    
    info "正在关联远程仓库: $remote_url"
    git remote add origin "$remote_url"
    
    # 验证远程地址
    git remote -v
    
    # 推送
    info "正在推送到远程仓库..."
    if git push -u origin "$branch_name"; then
        info "推送成功！"
        info "仓库地址: https://github.com/${github_user}/${repo_name}"
    else
        warn "推送失败，可能原因："
        warn "1. GitHub 上尚未创建仓库 ${repo_name}"
        warn "2. 远程仓库已有内容需要先拉取"
        printf "是否尝试先拉取再推送？(y/N): "
        read -r try_pull
        case "$try_pull" in
            [yY]|[yY][eE][sS])
                git pull origin "$branch_name" --allow-unrelated-histories || true
                git push -u origin "$branch_name"
                info "推送成功！"
                ;;
            *)
                error "请手动解决冲突后重试"
                ;;
        esac
    fi
}

# 主函数
main() {
    echo ""
    echo "========================================"
    echo "     Git 初始化 + SSH 推送脚本"
    echo "========================================"
    echo ""
    
    check_git
    check_existing_repo
    get_user_input
    check_ssh
    init_repo
    create_gitignore
    add_and_commit
    push_to_remote
    
    echo ""
    info "全部完成！你的代码已通过 SSH 推送到 GitHub"
    echo ""
}

# 执行主函数
main