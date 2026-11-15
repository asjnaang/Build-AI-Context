package com.asjnaang.buildaicontext

import com.intellij.openapi.options.Configurable
import com.intellij.openapi.ui.ComboBox
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBTextField
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.panel
import javax.swing.JComponent

class BaicSettingsConfigurable : Configurable {
    private val maxFileLines = JBTextField()
    private val outputDir = JBTextField()
    private val redact = JBCheckBox("Redact secrets in exported bundles")
    private val includeSecretFiles = JBCheckBox("Include secret-like files")
    private val projectOverview = JBCheckBox("Write project overview")
    private val updateGitignore = JBCheckBox("Update .gitignore")
    private val forceBundle = JBCheckBox("Force bundle oversized files")
    private val forceIgnored = JBCheckBox("Force ignored paths")
    private val split = JBCheckBox("Split gzip payloads under 19.9 MB")
    private val writeGraph = ComboBox(arrayOf("off", "txt", "json"))
    private val transport = ComboBox(arrayOf("tar-gz", "text"))
    private val excludePaths = JBTextField()
    private val forceIncludeFormats = JBTextField()
    private val task = JBTextField()
    private var panel: JComponent? = null

    override fun getDisplayName(): String = "Build AI Context"

    override fun createComponent(): JComponent {
        val ui = panel {
            row("Max file lines:") {
                cell(maxFileLines).align(AlignX.FILL)
            }
            row("Output directory:") {
                cell(outputDir).align(AlignX.FILL).comment("Empty uses exported_sources_{project}_{timestamp} under the project.")
            }
            row("Write graph:") {
                cell(writeGraph)
            }
            row("Transport:") {
                cell(transport).comment("gzip default matches CLI")
            }
            row("Exclude paths:") {
                cell(excludePaths).align(AlignX.FILL)
            }
            row("Force include formats:") {
                cell(forceIncludeFormats).align(AlignX.FILL)
            }
            row("Task for prompt:") {
                cell(task).align(AlignX.FILL)
            }
            row {
                cell(forceBundle)
            }
            row {
                cell(forceIgnored)
            }
            row {
                cell(split)
            }
            row {
                cell(redact)
            }
            row {
                cell(includeSecretFiles)
            }
            row {
                cell(projectOverview)
            }
            row {
                cell(updateGitignore)
            }
        }
        panel = ui
        reset()
        return ui
    }

    override fun isModified(): Boolean {
        val s = BaicSettings.getInstance().state
        return maxFileLines.text != s.maxFileLines.toString() ||
            outputDir.text != s.outputDir ||
            redact.isSelected != s.redact ||
            includeSecretFiles.isSelected != s.includeSecretFiles ||
            projectOverview.isSelected != s.projectOverview ||
            updateGitignore.isSelected != s.updateGitignore ||
            forceBundle.isSelected != s.forceBundle ||
            forceIgnored.isSelected != s.forceIgnored ||
            split.isSelected != s.split ||
            (writeGraph.selectedItem as String) != s.writeGraph ||
            (transport.selectedItem as String) != s.transport ||
            excludePaths.text != s.excludePaths ||
            forceIncludeFormats.text != s.forceIncludeFormats ||
            task.text != s.task
    }

    override fun apply() {
        val s = BaicSettings.getInstance().state
        s.maxFileLines = maxFileLines.text.toIntOrNull()?.coerceAtLeast(0) ?: 3000
        s.outputDir = outputDir.text.trim()
        s.redact = redact.isSelected
        s.includeSecretFiles = includeSecretFiles.isSelected
        s.projectOverview = projectOverview.isSelected
        s.updateGitignore = updateGitignore.isSelected
        s.writeGraph = writeGraph.selectedItem as String
        s.transport = transport.selectedItem as String
        s.forceBundle = forceBundle.isSelected
        s.forceIgnored = forceIgnored.isSelected
        s.split = split.isSelected
        s.excludePaths = excludePaths.text.trim()
        s.forceIncludeFormats = forceIncludeFormats.text.trim()
        s.task = task.text.trim()
    }

    override fun reset() {
        val s = BaicSettings.getInstance().state
        maxFileLines.text = s.maxFileLines.toString()
        outputDir.text = s.outputDir
        redact.isSelected = s.redact
        includeSecretFiles.isSelected = s.includeSecretFiles
        projectOverview.isSelected = s.projectOverview
        updateGitignore.isSelected = s.updateGitignore
        writeGraph.selectedItem = s.writeGraph
        transport.selectedItem = s.transport
        forceBundle.isSelected = s.forceBundle
        forceIgnored.isSelected = s.forceIgnored
        split.isSelected = s.split
        excludePaths.text = s.excludePaths
        forceIncludeFormats.text = s.forceIncludeFormats
        task.text = s.task
    }
}
