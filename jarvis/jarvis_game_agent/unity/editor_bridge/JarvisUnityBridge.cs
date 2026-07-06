// ════════════════════════════════════════════════════════════
// JarvisUnityBridge.cs
// Place this file in: Assets/Editor/JarvisUnityBridge.cs
// 
// Receives commands from Jarvis Game Agent via WebSocket + File polling.
// Runs inside Unity Editor — not in game builds.
// ════════════════════════════════════════════════════════════

#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System;
using System.IO;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using Newtonsoft.Json;   // or use Unity's JsonUtility

[InitializeOnLoad]
public class JarvisUnityBridge
{
    private static readonly string COMMANDS_DIR = Application.dataPath
        + "/../jarvis_game_agent/projects/_unity_commands/";
    private static readonly int WS_PORT  = 6400;
    private static readonly int HTTP_PORT = 6401;

    private static HttpListener _httpListener;
    private static Thread _httpThread;
    private static bool _running = false;

    // ─── Startup ───────────────────────────────────────────
    static JarvisUnityBridge()
    {
        EditorApplication.update     += PollCommandFiles;
        EditorApplication.quitting   += Shutdown;
        StartHttpServer();
        Debug.Log("[JarvisBridge] ✅ Unity Bridge active.");
    }

    // ─── HTTP Server ───────────────────────────────────────
    private static void StartHttpServer()
    {
        try
        {
            _httpListener = new HttpListener();
            _httpListener.Prefixes.Add($"http://localhost:{HTTP_PORT}/");
            _httpListener.Start();
            _running = true;

            _httpThread = new Thread(() =>
            {
                while (_running)
                {
                    try
                    {
                        var ctx     = _httpListener.GetContext();
                        var body    = new StreamReader(ctx.Request.InputStream).ReadToEnd();
                        var result  = HandleCommand(body);
                        var respBytes = Encoding.UTF8.GetBytes(result);
                        ctx.Response.ContentType = "application/json";
                        ctx.Response.OutputStream.Write(respBytes, 0, respBytes.Length);
                        ctx.Response.Close();
                    }
                    catch (Exception) { /* listener stopped */ }
                }
            });
            _httpThread.IsBackground = true;
            _httpThread.Start();
            Debug.Log($"[JarvisBridge] HTTP server on port {HTTP_PORT}");
        }
        catch (Exception e)
        {
            Debug.LogWarning("[JarvisBridge] HTTP server failed: " + e.Message);
        }
    }

    private static void Shutdown()
    {
        _running = false;
        _httpListener?.Stop();
    }

    // ─── File Bridge Polling ───────────────────────────────
    private static void PollCommandFiles()
    {
        if (!Directory.Exists(COMMANDS_DIR)) return;

        var files = Directory.GetFiles(COMMANDS_DIR, "cmd_*.json");
        foreach (var file in files)
        {
            try
            {
                var json    = File.ReadAllText(file);
                var result  = HandleCommand(json);
                var id      = Path.GetFileNameWithoutExtension(file).Replace("cmd_", "");
                var respPath = Path.Combine(COMMANDS_DIR, $"resp_{id}.json");
                File.WriteAllText(respPath, result);
                File.Delete(file);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[JarvisBridge] File cmd error: " + e.Message);
            }
        }
    }

    // ─── Command Router ────────────────────────────────────
    private static string HandleCommand(string json)
    {
        try
        {
            var cmd = JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
            if (cmd == null) return Err("Invalid JSON");

            string action = cmd.ContainsKey("action") ? cmd["action"].ToString() : "";
            Debug.Log($"[JarvisBridge] Action: {action}");

            switch (action)
            {
                case "import_asset":    return ImportAsset(cmd);
                case "create_scene":    return CreateScene(cmd);
                case "create_prefab":   return CreatePrefab(cmd);
                case "create_folders":  return CreateFolders(cmd);
                case "setup_lighting":  return SetupLighting(cmd);
                case "create_terrain":  return CreateTerrain(cmd);
                case "build":           return BuildGame(cmd);
                case "ping":            return Ok("pong");
                default:                return Err($"Unknown action: {action}");
            }
        }
        catch (Exception e)
        {
            return Err(e.Message);
        }
    }

    // ─── Handlers ──────────────────────────────────────────

    private static string ImportAsset(Dictionary<string, object> cmd)
    {
        string path   = cmd["path"].ToString();
        string folder = cmd.ContainsKey("target_folder")
            ? cmd["target_folder"].ToString() : "Assets/JarvisAssets";

        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
        AssetDatabase.Refresh();

        return Ok($"Imported: {path}");
    }

    private static string CreateScene(Dictionary<string, object> cmd)
    {
        string name = cmd.ContainsKey("scene_name")
            ? cmd["scene_name"].ToString() : "JarvisScene";

        string dir  = "Assets/JarvisGenerated/Scenes";
        if (!Directory.Exists(Application.dataPath + "/JarvisGenerated/Scenes"))
            Directory.CreateDirectory(Application.dataPath + "/JarvisGenerated/Scenes");

        var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
            UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects,
            UnityEditor.SceneManagement.NewSceneMode.Single
        );
        string scenePath = $"{dir}/{name}.unity";
        UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene, scenePath);
        AssetDatabase.Refresh();

        return Ok($"Scene created: {scenePath}");
    }

    private static string CreatePrefab(Dictionary<string, object> cmd)
    {
        string name   = cmd["name"].ToString();
        string folder = cmd.ContainsKey("folder")
            ? cmd["folder"].ToString() : "Assets/Prefabs";

        string dir = Application.dataPath + folder.Replace("Assets", "");
        if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

        var go = new GameObject(name);
        string path = $"{folder}/{name}.prefab";
        PrefabUtility.SaveAsPrefabAsset(go, path);
        UnityEngine.Object.DestroyImmediate(go);
        AssetDatabase.Refresh();

        return Ok($"Prefab created: {path}");
    }

    private static string CreateFolders(Dictionary<string, object> cmd)
    {
        // folders is a JSON array
        var foldersRaw = cmd["folders"].ToString();
        var folders = JsonConvert.DeserializeObject<List<string>>(foldersRaw);
        foreach (var folder in folders)
        {
            string dir = Application.dataPath + "/" + folder.Replace("Assets/", "");
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
        }
        AssetDatabase.Refresh();
        return Ok($"Created {folders.Count} folders");
    }

    private static string SetupLighting(Dictionary<string, object> cmd)
    {
        float intensity = cmd.ContainsKey("intensity")
            ? float.Parse(cmd["intensity"].ToString()) : 1.0f;

        var lights = UnityEngine.Object.FindObjectsOfType<Light>();
        foreach (var light in lights)
        {
            if (light.type == LightType.Directional)
                light.intensity = intensity;
        }
        return Ok("Lighting configured");
    }

    private static string CreateTerrain(Dictionary<string, object> cmd)
    {
        int size   = cmd.ContainsKey("size")   ? int.Parse(cmd["size"].ToString())   : 500;
        int height = cmd.ContainsKey("height") ? int.Parse(cmd["height"].ToString()) : 100;

        TerrainData td = new TerrainData();
        td.heightmapResolution = 513;
        td.size = new Vector3(size, height, size);

        string assetPath = "Assets/JarvisGenerated/JarvisTerrain.asset";
        AssetDatabase.CreateAsset(td, assetPath);

        Terrain.CreateTerrainGameObject(td);
        AssetDatabase.Refresh();

        return Ok($"Terrain created: {size}x{size}");
    }

    private static string BuildGame(Dictionary<string, object> cmd)
    {
        string platform = cmd.ContainsKey("platform")
            ? cmd["platform"].ToString() : "StandaloneWindows64";
        string output = cmd.ContainsKey("output_path")
            ? cmd["output_path"].ToString() : "./Build/JarvisGame.exe";

        var target = BuildTarget.StandaloneWindows64;
        if (platform.Contains("Mac"))   target = BuildTarget.StandaloneOSX;
        if (platform.Contains("Linux")) target = BuildTarget.StandaloneLinux64;

        var opts = new BuildPlayerOptions
        {
            scenes = new[] { "Assets/JarvisGenerated/Scenes/main_scene.unity" },
            locationPathName = output,
            target = target,
            options = BuildOptions.None
        };

        var report = BuildPipeline.BuildPlayer(opts);
        return Ok($"Build: {report.summary.result} at {output}");
    }

    // ─── Helpers ───────────────────────────────────────────
    private static string Ok(string msg) =>
        JsonConvert.SerializeObject(new { status = "ok", message = msg });
    private static string Err(string msg) =>
        JsonConvert.SerializeObject(new { status = "error", message = msg });
}
#endif
