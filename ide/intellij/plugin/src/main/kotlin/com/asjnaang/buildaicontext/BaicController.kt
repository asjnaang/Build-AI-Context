package com.asjnaang.buildaicontext

import com.asjnaang.buildaicontext.engine.Catalog
import com.asjnaang.buildaicontext.engine.EngineCanceled
import com.asjnaang.buildaicontext.engine.ExportOptions
import com.asjnaang.buildaicontext.engine.ExportResult
import com.asjnaang.buildaicontext.engine.HostState
import com.asjnaang.buildaicontext.engine.ScanOptions
import com.asjnaang.buildaicontext.engine.exportCatalog
import com.asjnaang.buildaicontext.engine.scan
import com.asjnaang.buildaicontext.engine.writeStandaloneFiletree
import com.asjnaang.buildaicontext.engine.writeStandaloneGraph
import com.intellij.ide.actions.RevealFileAction
import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.LocalFileSystem
import java.io.File
import java.nio.file.Path
import java.util.concurrent.CopyOnWriteArrayList

@Service(Service.Level.PROJECT)
class BaicController(private val project: Project) {
    val state = HostState()
    private val listeners = CopyOnWriteArrayList<() -> Unit>()

    fun addListener(listener: () -> Unit) {
        listeners.add(listener)
    }

    fun notifyChanged() {
        ApplicationManager.getApplication().invokeLater {
            listeners.forEach { it() }
        }
    }

    fun workspacePath(): String? = project.basePath

    fun scanProject() {
        val root = workspacePath() ?: return
        val settings = BaicSettings.getInstance().state
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Build AI Context: Scan", true) {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true
                indicator.text = "Scanning project…"
                try {
                    val catalog = scan(
                        root,
                        ScanOptions(
                            includeSecretFiles = settings.includeSecretFiles,
                            isCanceled = { indicator.isCanceled },
                        ),
                    )
                    if (indicator.isCanceled) return
                    state.maxFileLines = settings.maxFileLines
                    state.applyScan(catalog)
                    notifyChanged()
                } catch (_: EngineCanceled) {
                    return
                }
            }
        })
    }

    fun exportSelection() {
        val catalog: Catalog = state.catalog ?: run {
            Messages.showWarningDialog(project, "Scan the project first.", "Build AI Context")
            return
        }
        val selection = state.exportSelection()
        if (selection.files.isEmpty()) {
            Messages.showWarningDialog(project, "No files selected.", "Build AI Context")
            return
        }
        val settings = BaicSettings.getInstance().state
        state.maxFileLines = settings.maxFileLines
        var includeSecretFiles = settings.includeSecretFiles
        if (includeSecretFiles && !confirmSecrets()) includeSecretFiles = false
        val output = settings.outputDir.trim().ifEmpty { null }
        val graph = settings.writeGraph.takeIf { it == "txt" || it == "json" }
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Build AI Context: Export", true) {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true
                indicator.text = "Writing bundles…"
                try {
                    val result = exportCatalog(
                        catalog,
                        selection,
                        ExportOptions(
                            outputDir = output,
                            maxFileLines = state.exportMaxFileLines(),
                            redact = settings.redact,
                            projectOverview = settings.projectOverview,
                            writeGraph = graph,
                            updateGitignore = settings.updateGitignore,
                            includeSecretFiles = includeSecretFiles,
                            isCanceled = { indicator.isCanceled },
                        ),
                    )
                    if (indicator.isCanceled) return
                    notifyExport(result)
                } catch (_: EngineCanceled) {
                    return
                }
            }
        })
    }

    fun clearFilters() {
        state.clearFilters()
        notifyChanged()
    }

    fun generateFiletree() {
        val catalog = state.catalog ?: run {
            Messages.showWarningDialog(project, "Scan the project first.", "Build AI Context")
            return
        }
        val settings = BaicSettings.getInstance().state
        val path = writeStandaloneFiletree(catalog, settings.updateGitignore)
        notifyPath("Filetree written", path)
    }

    fun generateGraph() {
        val catalog = state.catalog ?: run {
            Messages.showWarningDialog(project, "Scan the project first.", "Build AI Context")
            return
        }
        val settings = BaicSettings.getInstance().state
        val format = if (settings.writeGraph == "json") "json" else "txt"
        val path = writeStandaloneGraph(catalog, format, settings.updateGitignore)
        notifyPath("Code graph written", path)
    }

    fun addPath(absPath: String) {
        val root = workspacePath() ?: return
        val rel = try {
            Path.of(root).relativize(Path.of(absPath)).toString().replace('\\', '/')
        } catch (_: Exception) {
            absPath
        }
        state.addPath(rel)
        if (state.catalog == null) scanProject()
        notifyChanged()
    }

    private fun confirmSecrets(): Boolean {
        return Messages.showYesNoDialog(
            project,
            "Include secret-like files (.env, keys, certificates) in this export? This may leak secrets into export bundles.",
            "Build AI Context",
            Messages.getWarningIcon(),
        ) == Messages.YES
    }

    private fun notifyPath(title: String, path: String) {
        ApplicationManager.getApplication().invokeLater {
            val group = NotificationGroupManager.getInstance().getNotificationGroup("Build AI Context")
            val notification = group.createNotification(title, path, NotificationType.INFORMATION)
            notification.addAction(
                NotificationAction.createSimple("Reveal") {
                    RevealFileAction.openFile(File(path))
                },
            )
            notification.notify(project)
        }
    }

    private fun notifyExport(result: ExportResult) {
        ApplicationManager.getApplication().invokeLater {
            val group = NotificationGroupManager.getInstance().getNotificationGroup("Build AI Context")
            val notification = group.createNotification(
                "Export complete",
                result.outputDir,
                NotificationType.INFORMATION,
            )
            notification.addAction(
                NotificationAction.createSimple("Reveal") {
                    RevealFileAction.openFile(File(result.outputDir))
                },
            )
            notification.addAction(
                NotificationAction.createSimple("Open Agent Contract") {
                    val vf = LocalFileSystem.getInstance().refreshAndFindFileByPath(result.promptPath)
                    if (vf != null) FileEditorManager.getInstance(project).openFile(vf, true)
                },
            )
            notification.notify(project)
        }
    }
}
