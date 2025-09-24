import os
import time
import json
import threading
import shutil
import requests
import sys
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox, filedialog, simpledialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from git import Repo, GitCommandError

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, folder_name, callback):
        self.folder_name = folder_name
        self.callback = callback
        self.changes_detected = False

    def on_modified(self, event):
        if not event.is_directory:
            self.changes_detected = True
            self.callback(self.folder_name)

    def on_created(self, event):
        if not event.is_directory:
            self.changes_detected = True
            self.callback(self.folder_name)

    def on_deleted(self, event):
        if not event.is_directory:
            self.changes_detected = True
            self.callback(self.folder_name)

class GitHubBrowser:
    def __init__(self, parent, on_select_callback):
        self.parent = parent
        self.on_select_callback = on_select_callback
        self.repo_url = ""
        self.branches = []
        self.token = ""
        
    def show(self):
        self.window = Toplevel(self.parent)
        self.window.title("Обзор GitHub репозитория")
        self.window.geometry("600x500")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Token input
        token_frame = ttk.Frame(self.window)
        token_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Label(token_frame, text="GitHub Token (для приватных репозиториев):").pack(anchor=W)
        self.token_var = StringVar()
        token_entry = ttk.Entry(token_frame, textvariable=self.token_var, width=50, show="*")
        token_entry.pack(fill=X, pady=(5, 0))
        ttk.Label(token_frame, text="Необязательно для публичных репозиториев", 
                 font=("Arial", 8), foreground="gray").pack(anchor=W)
        
        # URL input
        url_frame = ttk.Frame(self.window)
        url_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Label(url_frame, text="URL репозитория:").pack(side=LEFT)
        self.url_var = StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=50)
        url_entry.pack(side=LEFT, padx=5, fill=X, expand=True)
        url_entry.insert(0, "https://github.com/username/repository")
        
        ttk.Button(url_frame, text="Загрузить", command=self.load_repository).pack(side=LEFT)
        
        # Branches frame
        branches_frame = ttk.LabelFrame(self.window, text="Доступные ветки")
        branches_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.branches_listbox = Listbox(branches_frame, width=50, height=15)
        self.branches_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # Branch creation
        branch_frame = ttk.Frame(self.window)
        branch_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Label(branch_frame, text="Или создайте новую ветку:").pack(side=LEFT)
        self.new_branch_var = StringVar()
        new_branch_entry = ttk.Entry(branch_frame, textvariable=self.new_branch_var, width=20)
        new_branch_entry.pack(side=LEFT, padx=5)
        ttk.Button(branch_frame, text="Создать ветку", 
                  command=self.create_new_branch).pack(side=LEFT)
        
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Скачать выбранную ветку", 
                  command=self.download_selected).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", 
                  command=self.window.destroy).pack(side=RIGHT, padx=5)
        
    def load_repository(self):
        url = self.url_var.get().strip()
        self.token = self.token_var.get().strip()
        
        if not url:
            messagebox.showerror("Ошибка", "Введите URL репозитория")
            return
            
        if 'github.com' not in url:
            messagebox.showerror("Ошибка", "Введите корректный GitHub URL")
            return
            
        parts = url.replace('https://github.com/', '').split('/')
        if len(parts) < 2:
            messagebox.showerror("Ошибка", "Некорректный GitHub URL")
            return
            
        owner, repo = parts[0], parts[1]
        if repo.endswith('.git'):
            repo = repo[:-4]
            
        self.repo_url = f"https://github.com/{owner}/{repo}.git"
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        try:
            # Prepare headers with token if provided
            headers = {}
            if self.token:
                headers['Authorization'] = f'token {self.token}'
                # Update URL with token for private repos
                self.repo_url = f"https://{self.token}@github.com/{owner}/{repo}.git"
            
            # Get repository info
            repo_response = requests.get(api_url, headers=headers, timeout=10)
            if repo_response.status_code == 401:
                messagebox.showerror("Ошибка", "Неверный токен или недостаточно прав")
                return
            elif repo_response.status_code == 403:
                messagebox.showerror("Ошибка", "Превышен лимит запросов. Используйте токен для увеличения лимита.")
                return
            elif repo_response.status_code == 404:
                messagebox.showerror("Ошибка", "Репозиторий не найден. Возможно, он приватный и нужен токен.")
                return
            elif repo_response.status_code != 200:
                messagebox.showerror("Ошибка", f"Ошибка доступа: {repo_response.status_code}")
                return
            
            # Get branches
            branches_response = requests.get(f"{api_url}/branches", headers=headers, timeout=10)
            if branches_response.status_code != 200:
                messagebox.showerror("Ошибка", "Не удалось загрузить ветки")
                return
                
            self.branches = [branch['name'] for branch in branches_response.json()]
            self.branches_listbox.delete(0, END)
            for branch in self.branches:
                self.branches_listbox.insert(END, branch)
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки: {str(e)}")
            
    def create_new_branch(self):
        new_branch = self.new_branch_var.get().strip()
        if not new_branch:
            messagebox.showerror("Ошибка", "Введите имя новой ветки")
            return
            
        if new_branch in self.branches:
            messagebox.showwarning("Внимание", "Ветка с таким именем уже существует")
            return
            
        self.branches.append(new_branch)
        self.branches_listbox.delete(0, END)
        for branch in self.branches:
            self.branches_listbox.insert(END, branch)
        
        # Select the new branch
        self.branches_listbox.selection_set(self.branches.index(new_branch))
        messagebox.showinfo("Успех", f"Ветка '{new_branch}' будет создана при скачивании")

    def download_selected(self):
        selection = self.branches_listbox.curselection()
        branch = self.new_branch_var.get().strip()
        
        if not selection and not branch:
            messagebox.showerror("Ошибка", "Выберите или создайте ветку для скачивания")
            return
            
        if selection:
            branch = self.branches[selection[0]]
            
        self.window.destroy()
        self.on_select_callback(self.repo_url, branch)

class GitWatcherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Auto-Commit Watcher - Multi-Branch")
        self.root.geometry("1000x700")
        
        self.config_file = "watcher_config.json"
        self.watched_folders = {}
        self.observers = []
        
        self.load_config()
        self.create_widgets()
        self.start_monitoring()
        
        # Проверка обновлений при запуске (через 3 секунды)
        self.root.after(3000, self.check_self_update_on_start)

    def check_self_update_on_start(self):
        """Проверка обновлений при запуске"""
        try:
            def update_check():
                if self.check_self_update():
                    if messagebox.askyesno("Обновление", "Перезапустить программу сейчас?"):
                        self.restart_program()
            
            threading.Thread(target=update_check, daemon=True).start()
        except Exception as e:
            self.log_message(f"Ошибка при проверке обновлений: {str(e)}")

    def restart_program(self):
        """Перезапуск программы"""
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(N, S, E, W))
        
        # Title
        title_label = ttk.Label(main_frame, text="GitHub Auto-Commit Watcher - Multi-Branch", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=6, pady=(0, 20))
        
        # Controls frame
        controls_frame = ttk.LabelFrame(main_frame, text="Управление", padding="10")
        controls_frame.grid(row=1, column=0, columnspan=6, sticky=(E, W), pady=(0, 10))
        
        # Add folder button
        add_btn = ttk.Button(controls_frame, text="Добавить папку", command=self.add_folder)
        add_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Clone from GitHub button
        clone_btn = ttk.Button(controls_frame, text="Скачать с GitHub", command=self.browse_repository)
        clone_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Commit all button
        commit_all_btn = ttk.Button(controls_frame, text="Коммит всех изменений", 
                                   command=self.commit_all)
        commit_all_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Refresh button
        refresh_btn = ttk.Button(controls_frame, text="Обновить", command=self.refresh_status)
        refresh_btn.grid(row=0, column=3, padx=(0, 10))
        
        # Update button
        update_btn = ttk.Button(controls_frame, text="Проверить обновления", 
                               command=lambda: threading.Thread(target=self.check_self_update, daemon=True).start())
        update_btn.grid(row=0, column=4, padx=(0, 10))
        
        # Status treeview
        columns = ("folder", "local_path", "branch", "status", "changes", "last_commit")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=12)
        
        self.tree.heading("folder", text="Имя папки")
        self.tree.heading("local_path", text="Локальный путь")
        self.tree.heading("branch", text="Ветка")
        self.tree.heading("status", text="Статус")
        self.tree.heading("changes", text="Изменения")
        self.tree.heading("last_commit", text="Последний коммит")
        
        self.tree.column("folder", width=150)
        self.tree.column("local_path", width=250)
        self.tree.column("branch", width=100)
        self.tree.column("status", width=100)
        self.tree.column("changes", width=80)
        self.tree.column("last_commit", width=150)
        
        self.tree.grid(row=2, column=0, columnspan=6, sticky=(N, S, E, W), pady=(10, 0))
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(main_frame, orient=VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=2, column=6, sticky=(N, S))
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Action buttons frame
        action_frame = ttk.LabelFrame(main_frame, text="Действия с выбранной папкой", padding="10")
        action_frame.grid(row=3, column=0, columnspan=6, sticky=(E, W), pady=(10, 0))
        
        self.commit_btn = ttk.Button(action_frame, text="Коммит изменений", 
                                    command=self.commit_selected, state=DISABLED)
        self.commit_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.pull_btn = ttk.Button(action_frame, text="Обновить с GitHub", 
                                  command=self.pull_selected, state=DISABLED)
        self.pull_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.edit_btn = ttk.Button(action_frame, text="Изменить настройки", 
                                  command=self.edit_paths, state=DISABLED)
        self.edit_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.remove_btn = ttk.Button(action_frame, text="Удалить папку", 
                                    command=self.remove_folder, state=DISABLED)
        self.remove_btn.grid(row=0, column=3, padx=(0, 10))
        
        self.switch_branch_btn = ttk.Button(action_frame, text="Сменить ветку", 
                                           command=self.switch_branch, state=DISABLED)
        self.switch_branch_btn.grid(row=0, column=4, padx=(0, 10))
        
        self.refresh_branches_btn = ttk.Button(action_frame, text="Обновить ветки", 
                                              command=self.refresh_branches_selected, state=DISABLED)
        self.refresh_branches_btn.grid(row=0, column=5, padx=(0, 10))
        
        # Log text area
        log_label = ttk.Label(main_frame, text="Лог действий:")
        log_label.grid(row=4, column=0, sticky=W, pady=(20, 5))
        
        self.log_text = Text(main_frame, height=10, width=80)
        self.log_text.grid(row=5, column=0, columnspan=6, sticky=(N, S, E, W))
        
        log_scrollbar = ttk.Scrollbar(main_frame, orient=VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=5, column=6, sticky=(N, S))
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def log_message(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
        self.root.update()

    def browse_repository(self):
        """Показать браузер репозиториев GitHub"""
        browser = GitHubBrowser(self.root, self.clone_repository)
        browser.show()

    def clone_repository(self, repo_url, branch):
        """Клонировать репозиторий с выбранной веткой"""
        if not repo_url:
            return
        
        parent_folder = filedialog.askdirectory(title="Выберите папку для клонирования")
        if not parent_folder:
            return
        
        repo_name = repo_url.split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        target_path = os.path.join(parent_folder, repo_name)
        
        if os.path.exists(target_path):
            if not messagebox.askyesno("Папка существует", 
                                     f"Папка {target_path} уже существует.\nХотите перезаписать её?"):
                return
            shutil.rmtree(target_path)
        
        try:
            self.log_message(f"Клонирование репозитория: {repo_url} (ветка: {branch})")
            
            progress_window = Toplevel(self.root)
            progress_window.title("Клонирование...")
            progress_window.geometry("300x100")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            ttk.Label(progress_window, text="Клонирование...").pack(pady=10)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=X)
            progress_bar.start()
            
            def clone_thread():
                try:
                    # Клонируем репозиторий
                    repo = Repo.clone_from(repo_url, target_path, branch=branch)
                    
                    progress_window.destroy()
                    self.add_cloned_repo(repo, target_path, repo_url, branch)
                except Exception as e:
                    progress_window.destroy()
                    messagebox.showerror("Ошибка", f"Ошибка клонирования: {str(e)}")
            
            threading.Thread(target=clone_thread, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Ошибка клонирования: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось клонировать репозиторий: {str(e)}")

    def add_cloned_repo(self, repo, target_path, repo_url, branch):
        folder_name = Path(target_path).name
        
        self.watched_folders[target_path] = {
            'repo_path': target_path,
            'folder_name': folder_name,
            'remote_url': repo_url,
            'branch': branch,
            'handler': None,
            'observer': None,
            'repo': repo,
            'changes': False
        }
        
        self.save_config()
        self.start_folder_monitoring(target_path)
        self.refresh_status()
        self.log_message(f"Успешно клонирован и добавлен: {folder_name} (ветка: {branch})")

    def add_folder(self):
        folder_path = filedialog.askdirectory(title="Выберите папку с вашим ботом")
        if not folder_path:
            return
            
        folder_name = Path(folder_path).name
        
        if folder_path in self.watched_folders:
            messagebox.showwarning("Внимание", "Эта папка уже отслеживается!")
            return
        
        is_git_repo = False
        repo = None
        
        try:
            repo = Repo(folder_path)
            is_git_repo = True
            self.log_message(f"Найден существующий git репозиторий: {folder_name}")
        except:
            if messagebox.askyesno("Git репозиторий", 
                                 f"Папка '{folder_name}' не является git репозиторием.\n\nХотите инициализировать git в этой папке?"):
                try:
                    repo = Repo.init(folder_path)
                    is_git_repo = True
                    
                    try:
                        repo.git.add(A=True)
                        repo.index.commit("Initial commit")
                    except:
                        pass
                    
                    self.log_message(f"Инициализирован git репозиторий: {folder_name}")
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось инициализировать git: {str(e)}")
                    return
            else:
                return
        
        # Запрашиваем ветку
        branch = simpledialog.askstring("Ветка репозитория", 
                                      f"Введите имя ветки для проекта '{folder_name}':\n\nПо умолчанию: main",
                                      initialvalue="main")
        if not branch:
            branch = "main"
        
        remote_url = simpledialog.askstring("GitHub репозиторий", 
                                          f"Введите URL GitHub репозитория для '{folder_name}':\n\nПример: https://github.com/username/repository.git\nОставьте пустым, если не нужно настраивать удаленный репозиторий")
        
        if remote_url and repo is not None:
            try:
                # Настраиваем ветку
                self.setup_project_branch(repo, branch, remote_url)
            except Exception as e:
                self.log_message(f"Ошибка при настройке ветки: {str(e)}")
        
        self.watched_folders[folder_path] = {
            'repo_path': folder_path,
            'folder_name': folder_name,
            'remote_url': remote_url,
            'branch': branch,
            'handler': None,
            'observer': None,
            'repo': repo,
            'changes': False
        }
        
        self.save_config()
        self.start_folder_monitoring(folder_path)
        self.refresh_status()
        self.log_message(f"Добавлена папка: {folder_name} (ветка: {branch})")

    def setup_project_branch(self, repo, branch_name, remote_url):
        """Настройка ветки для проекта"""
        try:
            # Делаем fetch чтобы получить актуальные ветки
            if 'origin' in repo.remotes:
                origin = repo.remote('origin')
                origin.fetch()
            
            # Проверяем существование ветки локально и удаленно
            local_branches = [head.name for head in repo.heads]
            remote_branches = []
            
            if 'origin' in repo.remotes:
                for ref in repo.remotes.origin.refs:
                    if ref.remote_head != 'HEAD' and not ref.name.endswith('/HEAD'):
                        remote_branches.append(ref.remote_head)
            
            branch_exists_locally = branch_name in local_branches
            branch_exists_remotely = branch_name in remote_branches
            
            if branch_exists_locally:
                # Переключаемся на существующую локальную ветку
                repo.git.checkout(branch_name)
                self.log_message(f"Переключен на существующую ветку: {branch_name}")
            elif branch_exists_remotely:
                # Создаем локальную ветку для отслеживания удаленной
                repo.git.checkout('-b', branch_name, f'origin/{branch_name}')
                self.log_message(f"Создана локальная ветка для отслеживания удаленной: {branch_name}")
            else:
                # Создаем новую ветку
                repo.git.checkout('-b', branch_name)
                self.log_message(f"Создана новая ветка: {branch_name}")
            
            # Настраиваем remote
            if 'origin' in repo.remotes:
                origin = repo.remote('origin')
                origin.set_url(remote_url)
            else:
                repo.create_remote('origin', remote_url)
            
            self.log_message(f"Настроен remote origin: {remote_url}")
            
            # Пытаемся настроить upstream
            try:
                repo.git.push('--set-upstream', 'origin', branch_name)
                self.log_message(f"Установлен upstream для ветки: {branch_name}")
                return True
            except GitCommandError as e:
                if "rejected" in str(e):
                    self.log_message(f"Конфликт при пуше: {str(e)}")
                    return False
                else:
                    raise e
                    
        except Exception as e:
            self.log_message(f"Ошибка настройки ветки: {str(e)}")
            return False

    def refresh_branches(self, folder_path):
        """Принудительное обновление информации о ветках"""
        data = self.watched_folders[folder_path]
        repo = data['repo']
        
        try:
            if 'origin' in repo.remotes:
                origin = repo.remote('origin')
                origin.fetch()
                self.log_message(f"Обновлена информация о ветках для: {data['folder_name']}")
                return True
        except Exception as e:
            self.log_message(f"Ошибка обновления веток для {data['folder_name']}: {str(e)}")
        
        return False

    def refresh_branches_selected(self):
        """Обновить информацию о ветках для выбранного проекта"""
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if folder_path:
            if self.refresh_branches(folder_path):
                messagebox.showinfo("Успех", "Информация о ветках обновлена")
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить информацию о ветках")

    def switch_branch(self):
        """Смена ветки для выбранного проекта"""
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if not folder_path:
            return
        
        # Автоматически обновляем информацию о ветках при открытии диалога
        self.refresh_branches(folder_path)
        
        data = self.watched_folders[folder_path]
        repo = data['repo']
        
        # Получаем список доступных веток (локальных и удаленных)
        try:
            # Получаем локальные ветки
            local_branches = [head.name for head in repo.heads]
            
            # Получаем удаленные ветки
            remote_branches = []
            if 'origin' in repo.remotes:
                for ref in repo.remotes.origin.refs:
                    if ref.remote_head != 'HEAD' and not ref.name.endswith('/HEAD'):
                        branch_name = ref.name.replace('origin/', '')
                        remote_branches.append(branch_name)
            
            # Объединяем и убираем дубликаты
            all_branches = list(set(local_branches + remote_branches))
            all_branches.sort()
            
            current_branch = repo.active_branch.name
            
            # Диалог выбора ветки
            branch_window = Toplevel(self.root)
            branch_window.title("Смена ветки")
            branch_window.geometry("400x300")
            branch_window.transient(self.root)
            branch_window.grab_set()
            
            ttk.Label(branch_window, text=f"Текущая ветка: {current_branch}").pack(pady=10)
            ttk.Label(branch_window, text="Выберите новую ветку:").pack()
            
            # Фрейм для поиска
            search_frame = ttk.Frame(branch_window)
            search_frame.pack(fill=X, padx=20, pady=5)
            
            ttk.Label(search_frame, text="Поиск:").pack(side=LEFT)
            search_var = StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var)
            search_entry.pack(side=LEFT, padx=5, fill=X, expand=True)
            
            # Listbox для отображения веток
            listbox_frame = ttk.Frame(branch_window)
            listbox_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
            
            scrollbar = ttk.Scrollbar(listbox_frame)
            scrollbar.pack(side=RIGHT, fill=Y)
            
            branches_listbox = Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=10)
            branches_listbox.pack(side=LEFT, fill=BOTH, expand=True)
            scrollbar.config(command=branches_listbox.yview)
            
            # Заполняем список веток
            def update_branches_list(search_text=""):
                branches_listbox.delete(0, END)
                filtered_branches = [b for b in all_branches if search_text.lower() in b.lower()]
                for branch in filtered_branches:
                    branches_listbox.insert(END, branch)
                    if branch == current_branch:
                        branches_listbox.itemconfig(END, {'fg': 'green'})
            
            update_branches_list()
            
            # Обработчик поиска
            def on_search_change(*args):
                update_branches_list(search_var.get())
            
            search_var.trace('w', on_search_change)
            
            def do_switch():
                selection = branches_listbox.curselection()
                if not selection:
                    messagebox.showwarning("Внимание", "Выберите ветку")
                    return
                    
                new_branch = branches_listbox.get(selection[0])
                if new_branch == current_branch:
                    messagebox.showinfo("Информация", "Выбрана текущая ветка")
                    branch_window.destroy()
                    return
                
                try:
                    # Проверяем, существует ли ветка локально
                    if new_branch in local_branches:
                        # Переключаемся на существующую локальную ветку
                        repo.git.checkout(new_branch)
                    else:
                        # Создаем локальную ветку для отслеживания удаленной
                        repo.git.checkout('-b', new_branch, f'origin/{new_branch}')
                    
                    data['branch'] = new_branch
                    self.save_config()
                    self.refresh_status()
                    branch_window.destroy()
                    self.log_message(f"Переключен на ветку: {new_branch} для проекта {folder_name}")
                    messagebox.showinfo("Успех", f"Успешно переключен на ветку: {new_branch}")
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Ошибка переключения ветки: {str(e)}")
            
            ttk.Button(branch_window, text="Переключить", command=do_switch).pack(pady=10)
            
            # Автоматический выбор первой ветки в списке
            if branches_listbox.size() > 0:
                branches_listbox.selection_set(0)
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка получения списка веток: {str(e)}")

    def pull_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if folder_path:
            self.pull_changes(folder_path)

    def pull_changes(self, folder_path):
        data = self.watched_folders[folder_path]
        
        if not data.get('remote_url'):
            messagebox.showwarning("Внимание", "Для этой папки не указан удаленный репозиторий!")
            return
        
        try:
            progress_window = Toplevel(self.root)
            progress_window.title("Обновление с GitHub...")
            progress_window.geometry("300x100")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            ttk.Label(progress_window, text="Обновление с GitHub...").pack(pady=10)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=X)
            progress_bar.start()
            
            def pull_thread():
                try:
                    repo = data['repo']
                    branch = data.get('branch', 'main')
                    
                    # Переключаемся на нужную ветку
                    if repo.active_branch.name != branch:
                        repo.git.checkout(branch)
                    
                    current_commit = repo.head.commit.hexsha
                    
                    # Настраиваем upstream если нужно
                    if not hasattr(repo.active_branch, 'tracking_branch') or not repo.active_branch.tracking_branch():
                        self.setup_project_branch(repo, branch, data['remote_url'])
                    
                    origin = repo.remote('origin')
                    origin.fetch()
                    
                    pull_info = origin.pull()
                    new_commit = repo.head.commit.hexsha
                    
                    files_changed = (current_commit != new_commit)
                    
                    progress_window.destroy()
                    
                    if files_changed:
                        self.log_message(f"Успешно обновлено: {data['folder_name']} (ветка: {branch})")
                        messagebox.showinfo("Успех", "Проект успешно обновлен с GitHub!")
                        self.refresh_status()
                    else:
                        self.log_message(f"Нет новых изменений для: {data['folder_name']}")
                        messagebox.showinfo("Информация", "Нет новых изменений для загрузки.")
                    
                except Exception as e:
                    progress_window.destroy()
                    messagebox.showerror("Ошибка", f"Ошибка при обновлении: {str(e)}")
            
            threading.Thread(target=pull_thread, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Ошибка обновления {data['folder_name']}: {str(e)}")
            messagebox.showerror("Ошибка", f"Ошибка при обновлении: {str(e)}")

    def edit_paths(self):
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if not folder_path:
            return
        
        data = self.watched_folders[folder_path]
        
        edit_window = Toplevel(self.root)
        edit_window.title("Редактирование настроек")
        edit_window.geometry("500x300")
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        ttk.Label(edit_window, text="Редактирование настроек папки", font=("Arial", 12, "bold")).pack(pady=10)
        
        ttk.Label(edit_window, text="Имя папки:").pack(anchor=W, padx=20, pady=(10, 0))
        name_var = StringVar(value=data['folder_name'])
        name_entry = ttk.Entry(edit_window, textvariable=name_var, width=50)
        name_entry.pack(padx=20, pady=(5, 10), fill=X)
        
        ttk.Label(edit_window, text="Ветка:").pack(anchor=W, padx=20, pady=(0, 0))
        branch_var = StringVar(value=data.get('branch', 'main'))
        branch_entry = ttk.Entry(edit_window, textvariable=branch_var, width=50)
        branch_entry.pack(padx=20, pady=(5, 10), fill=X)
        
        ttk.Label(edit_window, text="URL GitHub репозитория:").pack(anchor=W, padx=20, pady=(0, 0))
        url_var = StringVar(value=data.get('remote_url', ''))
        url_entry = ttk.Entry(edit_window, textvariable=url_var, width=50)
        url_entry.pack(padx=20, pady=(5, 10), fill=X)
        
        auto_push_var = BooleanVar(value=data.get('auto_push', True))
        auto_push_cb = ttk.Checkbutton(edit_window, text="Автоматически пушить изменения после коммита", 
                                      variable=auto_push_var)
        auto_push_cb.pack(anchor=W, padx=20, pady=(5, 10))
        
        def save_changes():
            new_name = name_var.get().strip()
            new_branch = branch_var.get().strip()
            new_url = url_var.get().strip()
            
            if not new_name:
                messagebox.showwarning("Внимание", "Имя папки обязательно!")
                return
            
            if not new_branch:
                messagebox.showwarning("Внимание", "Имя ветки обязательно!")
                return
            
            self.watched_folders[folder_path]['folder_name'] = new_name
            self.watched_folders[folder_path]['branch'] = new_branch
            self.watched_folders[folder_path]['remote_url'] = new_url
            self.watched_folders[folder_path]['auto_push'] = auto_push_var.get()
            
            # Обновляем ветку если она изменилась
            if new_branch != data.get('branch', 'main'):
                try:
                    repo = self.watched_folders[folder_path]['repo']
                    self.setup_project_branch(repo, new_branch, new_url)
                except Exception as e:
                    self.log_message(f"Ошибка смены ветки: {str(e)}")
            
            if new_url and new_url != data.get('remote_url', ''):
                try:
                    repo = self.watched_folders[folder_path]['repo']
                    if 'origin' in repo.remotes:
                        origin = repo.remote('origin')
                        origin.set_url(new_url)
                    else:
                        repo.create_remote('origin', new_url)
                    self.log_message(f"Обновлен remote origin: {new_url}")
                except Exception as e:
                    self.log_message(f"Ошибка обновления remote: {str(e)}")
            
            self.save_config()
            self.refresh_status()
            edit_window.destroy()
            self.log_message(f"Обновлены настройки для: {new_name}")
        
        ttk.Button(edit_window, text="Сохранить", command=save_changes).pack(pady=10)

    def start_folder_monitoring(self, folder_path):
        folder_data = self.watched_folders[folder_path]
        
        def change_callback(folder_name):
            folder_data['changes'] = True
            self.refresh_status()
        
        event_handler = ChangeHandler(folder_data['folder_name'], change_callback)
        observer = Observer()
        observer.schedule(event_handler, folder_path, recursive=True)
        observer.start()
        
        folder_data['handler'] = event_handler
        folder_data['observer'] = observer

    def start_monitoring(self):
        for folder_path in self.watched_folders.keys():
            self.start_folder_monitoring(folder_path)
        self.refresh_status()
        self.log_message("Мониторинг запущен")

    def refresh_status(self):
        for item in self.tree.get_children():
            if self.tree.exists(item):  # Добавляем проверку существования элемента
                self.tree.delete(item)
        
        for folder_path, data in self.watched_folders.items():
            status = "Есть изменения" if data['changes'] else "Нет изменений"
            changes = "●" if data['changes'] else "○"
            branch = data.get('branch', 'main')
            
            try:
                last_commit = data['repo'].head.commit.committed_datetime.strftime("%Y-%m-%d %H:%M")
            except:
                last_commit = "Нет коммитов"
            
            item = self.tree.insert("", "end", values=(
                data['folder_name'],
                folder_path,
                branch,
                status,
                changes,
                last_commit
            ))
            
            if data['changes']:
                self.tree.set(item, "changes", "● Есть изменения")

    def on_tree_select(self, event):
        selection = self.tree.selection()
        if selection:
            self.commit_btn.config(state=NORMAL)
            self.pull_btn.config(state=NORMAL)
            self.edit_btn.config(state=NORMAL)
            self.remove_btn.config(state=NORMAL)
            self.switch_branch_btn.config(state=NORMAL)
            self.refresh_branches_btn.config(state=NORMAL)
        else:
            self.commit_btn.config(state=DISABLED)
            self.pull_btn.config(state=DISABLED)
            self.edit_btn.config(state=DISABLED)
            self.remove_btn.config(state=DISABLED)
            self.switch_branch_btn.config(state=DISABLED)
            self.refresh_branches_btn.config(state=DISABLED)

    def find_folder_by_name(self, folder_name):
        for path, data in self.watched_folders.items():
            if data['folder_name'] == folder_name:
                return path
        return None

    def commit_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if folder_path:
            self.commit_folder(folder_path)

    def commit_folder(self, folder_path):
        data = self.watched_folders[folder_path]
        
        if not data['changes']:
            messagebox.showinfo("Информация", "Нет изменений для коммита")
            return
        
        try:
            commit_window = Toplevel(self.root)
            commit_window.title("Коммит изменений")
            commit_window.geometry("400x300")
            commit_window.transient(self.root)
            commit_window.grab_set()
            
            ttk.Label(commit_window, text="Сообщение коммита:").pack(pady=(20, 5))
            
            commit_msg = Text(commit_window, height=4, width=50)
            commit_msg.pack(pady=5, padx=20, fill=BOTH, expand=True)
            commit_msg.insert("1.0", f"Auto-commit: {data['folder_name']} - {time.strftime('%Y-%m-%d %H:%M')}")
            
            settings_frame = ttk.Frame(commit_window)
            settings_frame.pack(pady=10, padx=20, fill=X)
            
            auto_push_var = BooleanVar(value=data.get('auto_push', True))
            auto_push_cb = ttk.Checkbutton(settings_frame, text="Автоматически пушить после коммита", 
                                          variable=auto_push_var)
            auto_push_cb.pack(anchor=W)
            
            def do_commit():
                message = commit_msg.get("1.0", END).strip()
                auto_push = auto_push_var.get()
                commit_window.destroy()
                
                data['auto_push'] = auto_push
                self.save_config()
                
                repo = data['repo']
                branch = data.get('branch', 'main')
                
                # Убеждаемся, что мы в правильной ветке
                if repo.active_branch.name != branch:
                    repo.git.checkout(branch)
                
                repo.git.add(A=True)
                repo.index.commit(message)
                
                if auto_push and data.get('remote_url'):
                    try:
                        origin = repo.remote(name='origin')
                        origin.push(branch)
                        self.log_message(f"Успешный коммит и пуш: {data['folder_name']} (ветка: {branch})")
                        messagebox.showinfo("Успех", "Изменения успешно запушены в GitHub!")
                    except GitCommandError as e:
                        if "no upstream branch" in str(e):
                            if self.setup_project_branch(repo, branch, data['remote_url']):
                                try:
                                    origin.push(branch)
                                    self.log_message(f"Успешный коммит и пуш (после настройки upstream): {data['folder_name']}")
                                    messagebox.showinfo("Успех", "Изменения успешно запушены в GitHub!")
                                except Exception as e2:
                                    self.log_message(f"Коммит выполнен, но пуш не удался после настройки upstream: {data['folder_name']} - {str(e2)}")
                                    messagebox.showwarning("Предупреждение", f"Коммит выполнен, но пуш не удался:\n{str(e2)}")
                            else:
                                self.log_message(f"Коммит выполнен, но не удалось настроить upstream: {data['folder_name']}")
                                messagebox.showwarning("Предупреждение", "Коммит выполнен, но не удалось настроить автоматическую синхронизацию с GitHub.")
                        else:
                            self.log_message(f"Коммит выполнен, но пуш не удался: {data['folder_name']} - {str(e)}")
                            messagebox.showwarning("Предупреждение", f"Коммит выполнен, но пуш не удался:\n{str(e)}")
                else:
                    self.log_message(f"Коммит выполнен (без пуша): {data['folder_name']} (ветка: {branch})")
                    messagebox.showinfo("Успех", "Коммит выполнен успешно!")
                
                data['changes'] = False
                self.refresh_status()
            
            ttk.Button(commit_window, text="Выполнить коммит", command=do_commit).pack(pady=10)
            
        except Exception as e:
            self.log_message(f"Ошибка коммита {data['folder_name']}: {str(e)}")
            messagebox.showerror("Ошибка", f"Ошибка при коммите: {str(e)}")

    def commit_all(self):
        has_changes = any(data['changes'] for data in self.watched_folders.values())
        
        if not has_changes:
            messagebox.showinfo("Информация", "Нет изменений для коммита")
            return
        
        if messagebox.askyesno("Подтверждение", "Коммитнуть все изменения во всех папках?"):
            for folder_path in self.watched_folders.keys():
                if self.watched_folders[folder_path]['changes']:
                    self.commit_folder(folder_path)

    def remove_folder(self):
        selection = self.tree.selection()
        if not selection:
            return
            
        folder_name = self.tree.item(selection[0])['values'][0]
        folder_path = self.find_folder_by_name(folder_name)
        
        if folder_path and messagebox.askyesno("Подтверждение", 
                                             f"Удалить папку {folder_name} из отслеживания?\n\nФайлы на диске не будут удалены."):
            if self.watched_folders[folder_path]['observer']:
                self.watched_folders[folder_path]['observer'].stop()
                self.watched_folders[folder_path]['observer'].join()
            
            del self.watched_folders[folder_path]
            self.save_config()
            self.refresh_status()
            self.log_message(f"Удалена папка: {folder_name}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.watched_folders = config.get('watched_folders', {})
                    
                    for folder_path, data in self.watched_folders.items():
                        try:
                            data['repo'] = Repo(data['repo_path'])
                            # Устанавливаем ветку по умолчанию если не указана
                            if 'branch' not in data:
                                data['branch'] = 'main'
                        except:
                            data['repo'] = None
            except Exception as e:
                self.watched_folders = {}
                self.log_message(f"Ошибка загрузки конфигурации: {str(e)}")

    def save_config(self):
        config = {'watched_folders': {}}
        
        for folder_path, data in self.watched_folders.items():
            config['watched_folders'][folder_path] = {
                'repo_path': data['repo_path'],
                'folder_name': data['folder_name'],
                'remote_url': data.get('remote_url', ''),
                'branch': data.get('branch', 'main'),
                'auto_push': data.get('auto_push', True),
                'changes': data['changes']
            }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def check_self_update(self):
        """Проверка обновлений программы"""
        try:
            # Конфигурация репозитория обновлений
            UPDATE_REPO_URL = "https://github.com/vasabi224/bots.git"
            UPDATE_BRANCH = "main"
            VERSION_FILE = "version.txt"
            
            # Текущая версия программы
            CURRENT_VERSION = "1.0.0"
            
            self.log_message("Проверка обновлений...")
            
            # Создаем временную папку для проверки обновлений
            temp_dir = os.path.join(os.path.dirname(__file__), "temp_update_check")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Клонируем репозиторий обновлений
            Repo.clone_from(UPDATE_REPO_URL, temp_dir, branch=UPDATE_BRANCH, depth=1)
            
            # Проверяем файл версии
            version_path = os.path.join(temp_dir, VERSION_FILE)
            if os.path.exists(version_path):
                with open(version_path, 'r', encoding='utf-8') as f:
                    latest_version = f.read().strip()
                
                if latest_version != CURRENT_VERSION:
                    if messagebox.askyesno("Обновление доступно", 
                                         f"Доступна новая версия {latest_version}\nТекущая версия: {CURRENT_VERSION}\n\nОбновить программу?"):
                        self.perform_self_update(temp_dir, latest_version)
                        return True
                else:
                    messagebox.showinfo("Обновление", "У вас установлена последняя версия программы")
            
            # Очищаем временную папку
            shutil.rmtree(temp_dir)
            return False
            
        except Exception as e:
            self.log_message(f"Ошибка проверки обновлений: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось проверить обновления: {str(e)}")
            return False

    def perform_self_update(self, update_dir, new_version):
        """Выполнение обновления программы"""
        try:
            # Создаем backup текущей версии
            backup_dir = os.path.join(os.path.dirname(__file__), f"backup_v{new_version}")
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            
            # Копируем текущие файлы в backup
            current_dir = os.path.dirname(__file__)
            shutil.copytree(current_dir, backup_dir, 
                           ignore=shutil.ignore_patterns('temp_*', 'backup_*', '.git'))
            
            # Копируем новые файлы (исключая временные файлы и конфиги)
            for item in os.listdir(update_dir):
                if item not in ['temp_update_check', 'backup_*', 'watcher_config.json']:
                    src_path = os.path.join(update_dir, item)
                    dst_path = os.path.join(current_dir, item)
                    
                    if os.path.isdir(src_path):
                        if os.path.exists(dst_path):
                            shutil.rmtree(dst_path)
                        shutil.copytree(src_path, dst_path)
                    else:
                        shutil.copy2(src_path, dst_path)
            
            self.log_message(f"Программа обновлена до версии {new_version}")
            messagebox.showinfo("Обновление завершено", 
                              f"Программа успешно обновлена до версии {new_version}\n"
                              f"Backup сохранен в: {backup_dir}\n\n"
                              f"Перезапустите программу для применения изменений.")
            
            # Очищаем временные файлы
            shutil.rmtree(update_dir)
            
        except Exception as e:
            self.log_message(f"Ошибка обновления: {str(e)}")
            messagebox.showerror("Ошибка обновления", f"Не удалось обновить программу: {str(e)}")

    def on_closing(self):
        for data in self.watched_folders.values():
            if data.get('observer'):
                data['observer'].stop()
                data['observer'].join()
        
        self.save_config()
        self.root.destroy()

def main():
    root = Tk()
    app = GitWatcherGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()