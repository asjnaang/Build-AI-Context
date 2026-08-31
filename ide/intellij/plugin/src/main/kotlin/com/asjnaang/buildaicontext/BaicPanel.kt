package com.asjnaang.buildaicontext

import com.asjnaang.buildaicontext.engine.loadPolicy
import com.intellij.openapi.actionSystem.ActionManager
import com.intellij.openapi.actionSystem.DefaultActionGroup
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
import javax.swing.JButton
import javax.swing.JCheckBox
import javax.swing.JComponent
import javax.swing.JPanel
import javax.swing.JTree
import javax.swing.event.DocumentEvent
import javax.swing.event.DocumentListener
import javax.swing.tree.DefaultTreeModel

class BaicPanel(private val project: Project) : com.intellij.openapi.ui.SimpleToolWindowPanel(true, true) {
    private val controller = project.getService(BaicController::class.java)
    private val categoryBoxes = LinkedHashMap<String, JCheckBox>()
    private val keywordField = JBTextField()
    private val treeRoot = CheckedTreeNode("files")
    private val treeModel = DefaultTreeModel(treeRoot)
    private val tree: CheckboxTree
    private var rebuilding = false

    init {
        tree = object : CheckboxTree(FileRenderer(), treeRoot) {
            override fun onNodeStateChanged(node: CheckedTreeNode) {
                if (rebuilding) return
                val row = node.userObject as? FileRow ?: return
                if (node.isChecked) controller.state.checked.add(row.relPath)
                else controller.state.checked.remove(row.relPath)
            }
        }
        tree.model = treeModel
        tree.isRootVisible = false

        val group = DefaultActionGroup().apply {
            add(ActionManager.getInstance().getAction("com.asjnaang.buildaicontext.Scan"))
            add(ActionManager.getInstance().getAction("com.asjnaang.buildaicontext.Export"))
        }
        toolbar = ActionManager.getInstance().createActionToolbar("BaicToolbar", group, true).apply {
            targetComponent = this@BaicPanel
        }.component

        setContent(buildUi())
        controller.addListener { reload() }
        reload()
    }

    private fun buildUi(): JComponent {
        val policy = loadPolicy()
        val categoriesPanel = JPanel().apply {
            layout = java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 8, 0)
            border = JBUI.Borders.empty(4)
        }
        for (category in policy.categoryDescriptions.keys) {
            val box = JCheckBox(category)
            box.addActionListener {
                val selected = categoryBoxes.filter { it.value.isSelected }.keys.toList()
                controller.state.filters.categories.clear()
                controller.state.filters.categories.addAll(selected)
                controller.state.catalog?.let { controller.state.applyScan(it) }
                reload()
            }
            categoryBoxes[category] = box
            categoriesPanel.add(box)
        }

        keywordField.emptyText.text = "Keywords"
        keywordField.document.addDocumentListener(object : DocumentListener {
            override fun insertUpdate(e: DocumentEvent) = applyKeyword()
            override fun removeUpdate(e: DocumentEvent) = applyKeyword()
            override fun changedUpdate(e: DocumentEvent) = applyKeyword()
        })

        val exportButton = JButton("Export").apply {
            addActionListener { controller.exportSelection() }
        }

        val filters = panel {
            row("Categories") {
                cell(categoriesPanel).align(AlignX.FILL)
            }
            row("Keywords") {
                cell(keywordField).align(AlignX.FILL)
            }
            row {
                cell(exportButton)
            }
        }

        val wrapper = JPanel(BorderLayout())
        wrapper.add(filters, BorderLayout.NORTH)
        wrapper.add(JBScrollPane(tree), BorderLayout.CENTER)
        return wrapper
    }

    private fun applyKeyword() {
        controller.state.setKeywords(keywordField.text.orEmpty())
        reload()
    }

    fun reload() {
        rebuilding = true
        try {
            val catalog = controller.state.catalog
            if (catalog != null) {
                val counts = catalog.files.groupingBy { it.category }.eachCount()
                for ((category, box) in categoryBoxes) {
                    val n = counts[category] ?: 0
                    box.text = "$category ($n)"
                    box.isSelected = category in controller.state.filters.categories
                }
            }
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
                    ),
                )
                node.isChecked = file.relPath in controller.state.checked
                dirNode(dir).add(node)
            }
            treeRoot.removeAllChildren()
            for (i in 0 until newRoot.childCount) {
                treeRoot.add(newRoot.getChildAt(i) as CheckedTreeNode)
            }
            treeModel.reload()
            expandFolders()
        } finally {
            rebuilding = false
        }
    }

    private fun expandFolders() {
        var row = 0
        while (row < tree.rowCount) {
            tree.expandRow(row)
            row++
        }
    }

    private data class FileRow(
        val relPath: String,
        val oversized: Boolean,
        val category: String,
        val name: String,
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
                    textRenderer.append(" (oversized)", SimpleTextAttributes.GRAYED_ATTRIBUTES)
                }
            } else {
                textRenderer.append(user?.toString() ?: "")
            }
        }
    }
}
