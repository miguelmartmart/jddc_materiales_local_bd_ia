# DEVIA CONFIGURATION CONTEXT: IMAGES/CONFIG
# Technical Guide for managing Image Generation Parameters (Domains & Workflows).

```json
{
  "namespace": "backend.modules.images.config",
  "purpose": "Defines rules for intent detection, prompt construction, and ComfyUI workflow mapping.",
  "file_structure": {
    "domains/": "YAML files defining semantic domains (e.g., hvac.yaml).",
    "workflows/": "JSON files defining ComfyUI node graphs (e.g., txt2img.json)."
  },
  "schemas": {
    "domain_yaml": {
      "file_pattern": "*.yaml",
      "structure": {
        "domain_triggers": ["List of keywords enabling this domain"],
        "canonical_objects": {
          "key": {
             "triggers": ["synonyms"],
             "english_term": "Exact prompt term (e.g. 'wall-mounted split')",
             "description": "internal doc"
          }
        },
        "attributes": {
          "category": {
             "key": {
                "triggers": ["synonyms"],
                "positive": "Prompt injection (e.g. 'yellow casing')",
                "negative": "Negative prompt injection (e.g. 'white casing')"
             }
          }
        },
        "negative_packs": {
          "pack_name": ["list", "of", "negative", "terms"]
        },
        "modes": {
          "mode_name": {
            "triggers": ["keywords"],
            "positive_prefix": "Start of prompt",
            "positive_suffix": "End of prompt",
            "required_negatives": ["pack_name"]
          }
        }
      },
      "rules": "Triggers are case-insensitive. 'attributes' must specify 'negative' if they override a default color."
    },
    "workflow_json": {
      "file_pattern": "*.json",
      "structure": "Standard ComfyUI API JSON format.",
      "dynamic_fields": {
        "3.inputs.seed": "Injected by JobManager",
        "6.inputs.text": "Injected Positive Prompt",
        "7.inputs.text": "Injected Negative Prompt"
      }
    }
  },
  "maintenance": {
    "adding_color": "Add to 'attributes.colors'. define triggers (es), positive (en), and negative (en).",
    "adding_domain": "Create new .yaml file in domains/. Register in Manager (auto-load)."
  }
}
```
