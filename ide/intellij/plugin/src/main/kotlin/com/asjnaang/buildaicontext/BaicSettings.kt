package com.asjnaang.buildaicontext

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage

@Service
@State(name = "BuildAiContextSettings", storages = [Storage("buildAiContext.xml")])
class BaicSettings : PersistentStateComponent<BaicSettings.State> {
    data class State(
        var maxFileLines: Int = 3000,
        var redact: Boolean = false,
        var includeSecretFiles: Boolean = false,
        var projectOverview: Boolean = false,
        var writeGraph: String = "off",
        var updateGitignore: Boolean = true,
        var outputDir: String = "",
    )

    private var state = State()

    override fun getState(): State = state

    override fun loadState(state: State) {
        this.state = state
    }

    companion object {
        fun getInstance(): BaicSettings =
            ApplicationManager.getApplication().getService(BaicSettings::class.java)
    }
}
