package com.bahrainunique.pricematcherremote

import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

data class Laptop(val name: String, val address: String, val token: String)

class MainActivity : AppCompatActivity() {
    private lateinit var spinner: Spinner
    private lateinit var connectionText: TextView
    private lateinit var logsText: TextView
    private lateinit var cycleText: TextView
    private lateinit var pageText: TextView
    private lateinit var checkedText: TextView
    private lateinit var updatedText: TextView
    private lateinit var skippedText: TextView
    private lateinit var errorsText: TextView
    private lateinit var currentSkuText: TextView
    private lateinit var lastActionText: TextView

    private val laptops = mutableListOf<Laptop>()
    private val executor = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private var polling = false

    private val pollTask = object : Runnable {
        override fun run() {
            if (polling) {
                refreshStatus()
                handler.postDelayed(this, 3000)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        spinner = findViewById(R.id.laptopSpinner)
        connectionText = findViewById(R.id.connectionText)
        logsText = findViewById(R.id.logsText)
        cycleText = findViewById(R.id.cycleText)
        pageText = findViewById(R.id.pageText)
        checkedText = findViewById(R.id.checkedText)
        updatedText = findViewById(R.id.updatedText)
        skippedText = findViewById(R.id.skippedText)
        errorsText = findViewById(R.id.errorsText)
        currentSkuText = findViewById(R.id.currentSkuText)
        lastActionText = findViewById(R.id.lastActionText)

        loadLaptops()
        rebuildSpinner()

        findViewById<Button>(R.id.addLaptopButton).setOnClickListener { showAddLaptopDialog() }
        findViewById<Button>(R.id.removeLaptopButton).setOnClickListener { removeSelectedLaptop() }
        findViewById<Button>(R.id.startButton).setOnClickListener { sendCommand("start") }
        findViewById<Button>(R.id.pauseButton).setOnClickListener { sendCommand("pause") }
        findViewById<Button>(R.id.resumeButton).setOnClickListener { sendCommand("resume") }
        findViewById<Button>(R.id.stopButton).setOnClickListener { sendCommand("stop") }
        findViewById<Button>(R.id.restartButton).setOnClickListener { sendCommand("restart") }

        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                refreshStatus()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    override fun onResume() {
        super.onResume()
        polling = true
        handler.post(pollTask)
    }

    override fun onPause() {
        super.onPause()
        polling = false
        handler.removeCallbacks(pollTask)
    }

    private fun selectedLaptop(): Laptop? =
        laptops.getOrNull(spinner.selectedItemPosition)

    private fun rebuildSpinner() {
        val names = if (laptops.isEmpty()) listOf("No laptops registered") else laptops.map { it.name }
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, names)
        if (laptops.isEmpty()) {
            connectionText.text = "Tap Add Laptop to connect."
        }
    }

    private fun showAddLaptopDialog() {
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 10, 40, 0)
        }

        val nameInput = EditText(this).apply { hint = "Office Laptop" }
        val addressInput = EditText(this).apply {
            hint = "http://100.x.x.x:8765"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        val tokenInput = EditText(this).apply { hint = "Access token from Windows app" }

        container.addView(nameInput)
        container.addView(addressInput)
        container.addView(tokenInput)

        AlertDialog.Builder(this)
            .setTitle("Add Laptop")
            .setView(container)
            .setPositiveButton("Save") { _, _ ->
                val name = nameInput.text.toString().trim()
                val address = addressInput.text.toString().trim().trimEnd('/')
                val token = tokenInput.text.toString().trim()
                if (name.isNotBlank() && address.isNotBlank() && token.isNotBlank()) {
                    laptops.add(Laptop(name, address, token))
                    saveLaptops()
                    rebuildSpinner()
                    spinner.setSelection(laptops.lastIndex)
                } else {
                    Toast.makeText(this, "Complete all fields.", Toast.LENGTH_LONG).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun removeSelectedLaptop() {
        val index = spinner.selectedItemPosition
        if (index !in laptops.indices) return
        AlertDialog.Builder(this)
            .setTitle("Remove laptop?")
            .setMessage(laptops[index].name)
            .setPositiveButton("Remove") { _, _ ->
                laptops.removeAt(index)
                saveLaptops()
                rebuildSpinner()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun refreshStatus() {
        val laptop = selectedLaptop() ?: return
        executor.execute {
            try {
                val json = request(laptop, "/api/status", "GET")
                runOnUiThread {
                    connectionText.text = "${json.optString("state", "Online")} • ${laptop.name}\n${laptop.address}"
                    val stats = json.optJSONObject("stats") ?: JSONObject()
                    cycleText.text = "Cycle\n${stats.optInt("cycle")}"
                    pageText.text = "Page\n${stats.optInt("page")}"
                    checkedText.text = "Checked\n${stats.optInt("checked")}"
                    updatedText.text = "Updated\n${stats.optInt("updated")}"
                    skippedText.text = "Skipped\n${stats.optInt("skipped")}"
                    errorsText.text = "Errors\n${stats.optInt("errors")}"
                    currentSkuText.text = "Current SKU: ${stats.optString("current_sku", "—").ifBlank { "—" }}"
                    lastActionText.text = "Last action: ${stats.optString("last_action", "—").ifBlank { "—" }}"

                    val logs = json.optJSONArray("logs") ?: JSONArray()
                    val lines = buildString {
                        for (i in 0 until logs.length()) append(logs.optString(i))
                    }
                    logsText.text = if (lines.isBlank()) "No logs yet." else lines
                }
            } catch (e: Exception) {
                runOnUiThread {
                    connectionText.text = "Offline or unreachable\n${e.message}"
                }
            }
        }
    }

    private fun sendCommand(command: String) {
        val laptop = selectedLaptop() ?: return
        executor.execute {
            try {
                request(laptop, "/api/$command", "POST")
                runOnUiThread {
                    Toast.makeText(this, command.replaceFirstChar { it.uppercase() } + " sent", Toast.LENGTH_SHORT).show()
                    refreshStatus()
                }
            } catch (e: Exception) {
                runOnUiThread {
                    Toast.makeText(this, e.message ?: "Command failed", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun request(laptop: Laptop, path: String, method: String): JSONObject {
        val connection = (URL(laptop.address + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 7000
            readTimeout = 7000
            setRequestProperty("Authorization", "Bearer ${laptop.token}")
            setRequestProperty("Content-Type", "application/json")
            if (method == "POST") {
                doOutput = true
                outputStream.use { it.write("{}".toByteArray()) }
            }
        }

        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (code !in 200..299) throw IllegalStateException("HTTP $code: $body")
        return JSONObject(body)
    }

    private fun saveLaptops() {
        val array = JSONArray()
        laptops.forEach {
            array.put(JSONObject().apply {
                put("name", it.name)
                put("address", it.address)
                put("token", it.token)
            })
        }
        getSharedPreferences("settings", MODE_PRIVATE).edit()
            .putString("laptops", array.toString())
            .apply()
    }

    private fun loadLaptops() {
        val raw = getSharedPreferences("settings", MODE_PRIVATE).getString("laptops", "[]") ?: "[]"
        val array = JSONArray(raw)
        for (i in 0 until array.length()) {
            val item = array.getJSONObject(i)
            laptops.add(Laptop(item.getString("name"), item.getString("address"), item.getString("token")))
        }
    }
}
