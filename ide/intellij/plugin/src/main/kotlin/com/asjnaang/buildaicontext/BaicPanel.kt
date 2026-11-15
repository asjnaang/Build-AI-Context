package com.asjnaang.buildaicontext

import com.asjnaang.buildaicontext.engine.loadPolicy
import com.intellij.openapi.project.Project
import com.intellij.ui.CheckboxTree
import com.intellij.ui.CheckedTreeNode
import com.intellij.ui.SimpleTextAttributes
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextField
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.panel
import com.intellij.util.ui.JBUI
import java.awt.BorderLayout
import java.awt.GridLayout
import javax.swing.BoxLayout
import javax.swing.JButton
import javax.swing.JCheckBox
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JTree
import javax.swing.event.DocumentEvent
import javax.swing.event.DocumentListener
import javax.swing.tree.DefaultTreeModel

class BaicPanel(private val project: Project) : com.intellij.openapi.ui.SimpleToolWindowPanel(true, true) {
    private val controller = project.getService(BaicController::class.java)
    private val categoryBoxes = LinkedHashMap<String, JCheckBox>()
    private val keywordField = JBTextField()
    private val searchField = JBTextField()
    private lateinit var formatBox: JComboBox<String>
    private val nameField = JBTextField()
    private val pathField = JBTextField()
    private val treeRoot = CheckedTreeNode("files")
    private val treeModel = DefaultTreeModel(treeRoot)
    private val tree: CheckboxTree
    private lateinit var summaryLabel: JLabel
    private lateinit var lastExportLabel: JLabel
    private lateinit var exportButton: JButton
    private var rebuilding = false

    init {
        tree = object : CheckboxTree(FileRenderer(), treeRoot) {
            override fun onNodeStateChanged(node: CheckedTreeNode) {
                if (rebuilding) return
                fun syncChecked(current: CheckedTreeNode) {
                    val row = current.userObject as? FileRow
                    if (row != null) {
                        if (current.isChecked) controller.state.checked.add(row.relPath)
                        else controller.state.checked.remove(row.relPath)
                    }
                    for (index in 0 until current.childCount) {
                        syncChecked(current.getChildAt(index) as CheckedTreeNode)
                    }
                }
                syncChecked(node)
                updateSummary()
            }
        }
        tree.model = treeModel
        tree.isRootVisible = false

        setContent(buildUi())
        controller.addListener { reload() }
        reload()
        controller.scanProject()
    }

    private fun buildUi(): JComponent {
        val policy = loadPolicy()
        val categoriesPanel = JPanel().apply {
            layout = GridLayout(0, 1, 4, 2)
            border = JBUI.Borders.empty(4)
        }
        for (category in policy.categoryDescriptions.keys) {
            val box = JCheckBox(category)
            box.addActionListener {
                if (rebuilding) return@addActionListener
                val selected = categoryBoxes.filter { it.value.isSelected }.keys.toList()
                controller.state.filters.categoriesConstrained = true
                controller.state.filters.categories.clear()
                controller.state.filters.categories.addAll(selected)
                controller.state.catalog?.let { controller.state.applyScan(it) }
                reload()
            }
            categoryBoxes[category] = box
            categoriesPanel.add(box)
        }

        keywordField.emptyText.text = "Keywords"
        nameField.emptyText.text = "Filename substring"
        pathField.emptyText.text = "Path chips (comma-separated)"
        listen(keywordField) { controller.state.setKeywords(keywordField.text.orEmpty()) }
        listen(nameField) { controller.state.setNameFilters(nameField.text.orEmpty()) }
        listen(pathField) { controller.state.setPaths(pathField.text.orEmpty()) }
        searchField.emptyText.text = "Search files, paths, categories"
        listen(searchField) { controller.state.searchQuery = searchField.text.orEmpty() }
        formatBox = JComboBox(arrayOf("All formats"))
        formatBox.addActionListener {
            if (rebuilding) return@addActionListener
            controller.state.formatFilter = (formatBox.selectedItem as? String).orEmpty().takeUnless { it == "All formats" }.orEmpty()
            reload()
        }

        exportButton = JButton("Export").apply {
            alignmentX = java.awt.Component.LEFT_ALIGNMENT
            maximumSize = java.awt.Dimension(Int.MAX_VALUE, preferredSize.height)
            addActionListener { controller.exportSelection() }
        }

        val settings = BaicSettings.getInstance().state
        val transportBox = JComboBox(arrayOf("tar-gz", "text")).apply {
            selectedItem = settings.transport
            addActionListener {
                BaicSettings.getInstance().state.transport = selectedItem as String
            }
        }
        val forceBundleBox = JCheckBox("Force bundle oversized files").apply {
            isSelected = settings.forceBundle
            addActionListener { BaicSettings.getInstance().state.forceBundle = isSelected }
        }
        val forceIgnoredBox = JCheckBox("Force ignored (uses Paths, like --force-ignored --paths)").apply {
            isSelected = settings.forceIgnored
            addActionListener {
                BaicSettings.getInstance().state.forceIgnored = isSelected
                controller.scanProject()
            }
        }
        val splitBox = JCheckBox("Split gzip payloads under 19.9 MB").apply {
            isSelected = settings.split
            addActionListener { BaicSettings.getInstance().state.split = isSelected }
        }
        val excludeField = JBTextField(settings.excludePaths).apply {
            emptyText.text = "history/,docs/,tests/"
        }
        listen(excludeField) {
            BaicSettings.getInstance().state.excludePaths = excludeField.text.orEmpty()
        }
        val formatsField = JBTextField(settings.forceIncludeFormats).apply {
            emptyText.text = ".sqlite3"
        }
        listen(formatsField) {
            BaicSettings.getInstance().state.forceIncludeFormats = formatsField.text.orEmpty()
        }
        val taskField = JBTextField(settings.task).apply {
            emptyText.text = "Task for baic_prompt.md"
        }
        listen(taskField) { BaicSettings.getInstance().state.task = taskField.text.orEmpty() }
        val filters = panel {
            row("Task") { cell(taskField).align(AlignX.FILL) }
            row { cell(forceBundleBox) }
            row { cell(forceIgnoredBox) }
            row { cell(splitBox) }
            row("Exclude paths") {
                cell(excludeField).align(AlignX.FILL)
            }
            row("Force include formats") {
                cell(formatsField).align(AlignX.FILL)
            }
            row("Categories") {
                cell(categoriesPanel).align(AlignX.FILL)
            }
            row("Keywords") {
                cell(keywordField).align(AlignX.FILL)
            }
            row("Filename") {
                cell(nameField).align(AlignX.FILL)
            }
            row("Paths") {
                cell(pathField).align(AlignX.FILL)
            }
        }
        val filtersScroll = JBScrollPane(filters).apply {
            preferredSize = java.awt.Dimension(280, 230)
            maximumSize = java.awt.Dimension(Int.MAX_VALUE, 230)
            isVisible = false
        }

        val filtersButton = JButton("Show options").apply {
            addActionListener {
                filtersScroll.isVisible = !filtersScroll.isVisible
                text = if (filtersScroll.isVisible) "Hide options" else "Show options"
                parent.revalidate()
            }
        }
        summaryLabel = JLabel("Cataloging this project…")
        lastExportLabel = JLabel("No export yet")
        val actions = JPanel(java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 6, 0)).apply {
            add(JButton("Restore gzip").apply { addActionListener { controller.restoreFromDisk() } })
            add(JButton("Refresh catalog").apply { addActionListener { controller.scanProject() } })
        }
        val packageRow = JPanel(java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 6, 0)).apply {
            add(JLabel("Package"))
            add(transportBox)
        }
        val searchControls = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            alignmentX = java.awt.Component.LEFT_ALIGNMENT
            add(JLabel("Search files"))
            add(searchField)
            add(JPanel(java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 6, 0)).apply {
                add(JLabel("File format"))
                add(formatBox)
            })
            add(JButton("Select all results").apply {
                alignmentX = java.awt.Component.LEFT_ALIGNMENT
                addActionListener {
                    controller.state.selectAllResults()
                    reload()
                }
            })
        }
        val header = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            border = JBUI.Borders.empty(8)
            summaryLabel.alignmentX = java.awt.Component.LEFT_ALIGNMENT
            packageRow.alignmentX = java.awt.Component.LEFT_ALIGNMENT
            actions.alignmentX = java.awt.Component.LEFT_ALIGNMENT
            filtersButton.alignmentX = java.awt.Component.LEFT_ALIGNMENT
            filtersScroll.alignmentX = java.awt.Component.LEFT_ALIGNMENT
            add(summaryLabel)
            add(searchControls)
            add(exportButton)
            add(packageRow)
            add(actions)
            add(filtersButton)
            add(filtersScroll)
            add(JPanel(java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 6, 0)).apply {
                add(lastExportLabel)
                add(JButton("Open last").apply { addActionListener { controller.openLastExport() } })
            })
        }
        val wrapper = JPanel(BorderLayout())
        wrapper.add(header, BorderLayout.NORTH)
        val selection = JPanel(BorderLayout()).apply {
            border = JBUI.Borders.empty(0, 8, 8, 8)
            add(JLabel("Files · uncheck to omit"), BorderLayout.NORTH)
            add(JBScrollPane(tree), BorderLayout.CENTER)
        }
        wrapper.add(selection, BorderLayout.CENTER)
        return wrapper
    }

    private fun listen(field: JBTextField, apply: () -> Unit) {
        field.document.addDocumentListener(object : DocumentListener {
            override fun insertUpdate(e: DocumentEvent) = onChange()
            override fun removeUpdate(e: DocumentEvent) = onChange()
            override fun changedUpdate(e: DocumentEvent) = onChange()
            private fun onChange() {
                if (rebuilding) return
                apply()
                reload()
            }
        })
    }

    fun reload() {
        rebuilding = true
        try {
            val catalog = controller.state.catalog
            if (catalog != null) {
                val formats = listOf("All formats") + controller.state.availableFormats()
                if ((0 until formatBox.itemCount).map { formatBox.getItemAt(it) } != formats) {
                    formatBox.removeAllItems()
                    formats.forEach { formatBox.addItem(it) }
                }
                formatBox.selectedItem = controller.state.formatFilter.ifEmpty { "All formats" }
                val counts = catalog.files.groupingBy { it.category }.eachCount()
                for ((category, box) in categoryBoxes) {
                    val n = counts[category] ?: 0
                    box.text = "${category.replace('_', ' ')} ($n)"
                    box.isVisible = n > 0
                    box.isSelected = if (!controller.state.filters.categoriesConstrained) {
                        n > 0
                    } else {
                        controller.state.categoryChecked(category)
                    }
                }
            }
            syncField(keywordField, controller.state.filters.keywords.joinToString(" "))
            syncField(searchField, controller.state.searchQuery)
            syncField(nameField, controller.state.filters.nameFilters.joinToString(" "))
            syncField(pathField, controller.state.filters.paths.joinToString(", "))
            val (included, oversized) = controller.state.visibleFiles()
            val oversizedSet = oversized.map { it.relPath }.toSet()
            val all = included + oversized
            val newRoot = CheckedTreeNode("files")
            val dirNodes = HashMap<String, CheckedTreeNode>()
            dirNodes[""] = newRoot
            fun dirNode(dir: String): CheckedTreeNode {
                dirNodes[dir]?.let { return it }
                val parent = if (dir.contains('/')) dir.substringBeforeLast('/') else ""
                val name = dir.substringAfterLast('/')
                val node = CheckedTreeNode(name)
                dirNode(parent).add(node)
                dirNodes[dir] = node
                return node
            }
            for (file in all.sortedBy { it.relPath }) {
                val dir = if (file.relPath.contains('/')) file.relPath.substringBeforeLast('/') else ""
                val name = file.relPath.substringAfterLast('/')
                val node = CheckedTreeNode(
                    FileRow(
                        relPath = file.relPath,
                        oversized = file.relPath in oversizedSet,
                        category = file.category,
                        name = name,
                        lineCount = file.lineCount,
                    ),
                )
                node.isChecked = file.relPath in controller.state.checked
                dirNode(dir).add(node)
            }
            treeRoot.removeAllChildren()
            while (newRoot.childCount > 0) {
                treeRoot.add(newRoot.getChildAt(0) as CheckedTreeNode)
            }
            treeModel.reload()
            updateSummary()
        } finally {
            rebuilding = false
        }
    }

    private fun syncField(field: JBTextField, value: String) {
        if (field.text != value) field.text = value
    }

    private fun updateSummary() {
        val catalog = controller.state.catalog
        lastExportLabel.text = controller.lastExport?.let { "Last: ${java.io.File(it.outputDir).name}" } ?: "No export yet"
        if (catalog == null) {
            summaryLabel.text = "Cataloging this project… Export waits for the catalog."
            exportButton.text = "Export"
            exportButton.isEnabled = true
            return
        }
        val (included, oversized) = controller.state.visibleFiles()
        val visible = (included + oversized).mapTo(HashSet()) { it.relPath }
        val selected = controller.state.checked.count { it in visible }
        val transport = BaicSettings.getInstance().state.transport.ifBlank { "tar-gz" }
        summaryLabel.text = "<html>${visible.size} results · $selected selected · $transport<br>${oversized.size} large files start unchecked</html>"
        exportButton.text = "Export $selected files"
        exportButton.isEnabled = selected > 0
    }

    private data class FileRow(
        val relPath: String,
        val oversized: Boolean,
        val category: String,
        val name: String,
        val lineCount: Int,
    ) {
        override fun toString(): String = name
    }

    private class FileRenderer : CheckboxTree.CheckboxTreeCellRenderer() {
        override fun customizeRenderer(
            tree: JTree,
            value: Any?,
            selected: Boolean,
            expanded: Boolean,
            leaf: Boolean,
            row: Int,
            hasFocus: Boolean,
        ) {
            val node = value as? CheckedTreeNode ?: return
            val user = node.userObject
            if (user is FileRow) {
                textRenderer.append(user.name)
                textRenderer.append(" (${user.lineCount} lines)", SimpleTextAttributes.GRAYED_ATTRIBUTES)
                if (user.oversized) {
                    textRenderer.append(" (oversized)", SimpleTextAttributes.GRAYED_ATTRIBUTES)
                }
            } else {
                textRenderer.append(user?.toString() ?: "")
            }
        }
    }
}
