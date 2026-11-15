package com.asjnaang.buildaicontext

import com.asjnaang.buildaicontext.engine.loadPolicy
import com.intellij.openapi.project.Project
import com.intellij.ui.CheckboxTree
import com.intellij.ui.CheckedTreeNode
import com.intellij.ui.SimpleTextAttributes
import com.intellij.ui.components.ActionLink
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextField
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.panel
import com.intellij.util.ui.JBUI
import com.intellij.util.ui.UIUtil
import java.awt.BorderLayout
import java.awt.Component
import java.awt.Dimension
import java.awt.FlowLayout
import java.awt.GridLayout
import javax.swing.Box
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
    private lateinit var selectAllBox: JCheckBox
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
        pathField.emptyText.text = "Paths"
        listen(keywordField) { controller.state.setKeywords(keywordField.text.orEmpty()) }
        listen(nameField) { controller.state.setNameFilters(nameField.text.orEmpty()) }
        listen(pathField) { controller.state.setPaths(pathField.text.orEmpty()) }
        searchField.emptyText.text = "Search files…"
        listen(searchField) { controller.state.searchQuery = searchField.text.orEmpty() }
        formatBox = JComboBox(arrayOf("All formats"))
        formatBox.addActionListener {
            if (rebuilding) return@addActionListener
            controller.state.formatFilter = (formatBox.selectedItem as? String).orEmpty().takeUnless { it == "All formats" }.orEmpty()
            reload()
        }

        exportButton = JButton("Export").apply {
            addActionListener { controller.exportSelection() }
        }
        selectAllBox = JCheckBox("Select all results").apply {
            addActionListener {
                if (rebuilding) return@addActionListener
                controller.state.setResultsChecked(isSelected)
                reload()
            }
        }

        val settings = BaicSettings.getInstance().state
        val transportBox = JComboBox(arrayOf("gzip", "text")).apply {
            selectedItem = if (settings.transport == "text") "text" else "gzip"
            addActionListener {
                BaicSettings.getInstance().state.transport = if (selectedItem == "text") "text" else "tar-gz"
                updateSummary()
            }
        }
        val forceBundleBox = JCheckBox("Include large files").apply {
            isSelected = settings.forceBundle
            addActionListener { BaicSettings.getInstance().state.forceBundle = isSelected }
        }
        val forceIgnoredBox = JCheckBox("Include ignored paths").apply {
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
            row("Exclude paths") { cell(excludeField).align(AlignX.FILL) }
            row("Extra formats") { cell(formatsField).align(AlignX.FILL) }
            row("Categories") { cell(categoriesPanel).align(AlignX.FILL) }
            row("Keywords") { cell(keywordField).align(AlignX.FILL) }
            row("Filename") { cell(nameField).align(AlignX.FILL) }
            row("Paths") { cell(pathField).align(AlignX.FILL) }
        }
        val filtersScroll = JBScrollPane(filters).apply {
            preferredSize = Dimension(280, 220)
            maximumSize = Dimension(Int.MAX_VALUE, 220)
            isVisible = false
        }
        val filtersButton = JButton("Selection  Expand ▾").apply {
            addActionListener {
                filtersScroll.isVisible = !filtersScroll.isVisible
                text = if (filtersScroll.isVisible) "Selection  Collapse ▴" else "Selection  Expand ▾"
                parent?.revalidate()
            }
        }

        summaryLabel = JLabel("Cataloging this project…")
        lastExportLabel = JLabel("No export yet")

        val header = column().apply {
            border = JBUI.Borders.empty(10, 12, 4, 12)
            add(stretch(searchField))
            add(Box.createVerticalStrut(6))
            add(stretch(optionRow("File format", formatBox)))
            add(Box.createVerticalStrut(6))
            add(stretch(summaryLabel))
            add(Box.createVerticalStrut(8))
            add(stretch(exportButton))
            add(Box.createVerticalStrut(6))
            add(stretch(selectAllBox))
            add(
                stretch(
                    JPanel(FlowLayout(FlowLayout.LEFT, 12, 0)).apply {
                        isOpaque = false
                        add(ActionLink("Refresh") { controller.scanProject() })
                        add(ActionLink("Restore gzip") { controller.restoreFromDisk() })
                    },
                ),
            )
        }

        val files = JPanel(BorderLayout()).apply {
            border = JBUI.Borders.empty(0, 12, 0, 12)
            add(sectionLabel("Files"), BorderLayout.NORTH)
            add(JBScrollPane(tree), BorderLayout.CENTER)
        }

        val lastExportRow = JPanel(FlowLayout(FlowLayout.LEFT, 8, 0)).apply {
            isOpaque = false
            add(lastExportLabel)
            add(ActionLink("Open folder") { controller.openLastExport() })
            add(ActionLink("baic_prompt.md") { controller.openLastPrompt() })
        }
        val south = column().apply {
            border = JBUI.Borders.empty(4, 12, 10, 12)
            add(sectionLabel("Options"))
            add(stretch(optionRow("Package", transportBox)))
            add(stretch(filtersButton))
            add(stretch(filtersScroll))
            add(JLabel("Paths, keywords and CLI overrides expand here").apply {
                foreground = UIUtil.getContextHelpForeground()
                alignmentX = Component.LEFT_ALIGNMENT
            })
            add(sectionLabel("Last export"))
            add(stretch(lastExportRow))
        }

        val wrapper = JPanel(BorderLayout())
        wrapper.add(header, BorderLayout.NORTH)
        wrapper.add(files, BorderLayout.CENTER)
        wrapper.add(south, BorderLayout.SOUTH)
        return wrapper
    }

    private fun column(): JPanel = JPanel().apply {
        layout = BoxLayout(this, BoxLayout.Y_AXIS)
        alignmentX = Component.LEFT_ALIGNMENT
    }

    private fun stretch(component: JComponent): JComponent {
        component.alignmentX = Component.LEFT_ALIGNMENT
        val height = component.preferredSize.height.coerceAtLeast(24)
        component.maximumSize = Dimension(Int.MAX_VALUE, height)
        return component
    }

    private fun optionRow(label: String, field: JComponent): JPanel =
        JPanel(BorderLayout(8, 0)).apply {
            isOpaque = false
            add(JLabel(label), BorderLayout.WEST)
            add(field, BorderLayout.EAST)
        }

    private fun sectionLabel(text: String): JLabel =
        JLabel(text.uppercase()).apply {
            font = font.deriveFont(font.size2D - 1f)
            foreground = UIUtil.getContextHelpForeground()
            border = JBUI.Borders.empty(10, 0, 6, 0)
            alignmentX = Component.LEFT_ALIGNMENT
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
            exportButton.text = "Export 0 files"
            exportButton.isEnabled = true
            selectAllBox.isSelected = false
            return
        }
        val (included, oversized) = controller.state.visibleFiles()
        val visible = (included + oversized).mapTo(HashSet()) { it.relPath }
        val selected = controller.state.checked.count { it in visible }
        val transport = if (BaicSettings.getInstance().state.transport == "text") "text" else "gzip"
        val large = if (oversized.isEmpty()) "" else "<br>${oversized.size} large files start unchecked"
        summaryLabel.text = "<html>${visible.size} results · $selected selected · $transport$large</html>"
        exportButton.text = "Export $selected files"
        exportButton.isEnabled = selected > 0
        selectAllBox.isSelected = controller.state.allResultsChecked()
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
                if (user.oversized) {
                    textRenderer.append(" large", SimpleTextAttributes.GRAYED_ATTRIBUTES)
                }
            } else {
                textRenderer.append(user?.toString() ?: "")
            }
        }
    }
}
