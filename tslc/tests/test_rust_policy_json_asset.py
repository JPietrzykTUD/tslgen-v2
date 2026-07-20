"""Host-rustc evidence for the strict generated policy JSON parser."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

from tslc.compiler_assets import load_default_render_assets


@pytest.mark.generated_build
def test_rust_policy_json_asset_is_strict_and_std_only(tmp_path: Path) -> None:
    rustc = shutil.which("rustc")
    if rustc is None:
        pytest.skip("rustc is required")

    asset = tmp_path / "tsl_rust_policy_json.rs"
    driver = tmp_path / "driver.rs"
    binary = tmp_path / "policy-json-test"
    asset.write_text(
        load_default_render_assets().text("tsl_rust_policy_json.rs"),
        encoding="utf-8",
    )
    driver.write_text(_RUST_DRIVER, encoding="utf-8")

    compiled = subprocess.run(
        (
            rustc,
            "--edition=2021",
            "-Dwarnings",
            str(driver),
            "-o",
            str(binary),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stderr

    completed = subprocess.run(
        (str(binary),),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "strict policy JSON parser passed\n"


_RUST_DRIVER = textwrap.dedent(
    r'''
    #[path = "tsl_rust_policy_json.rs"]
    mod policy_json;

    use policy_json::{
        parse_json, JsonNumber, JsonValue, MAX_JSON_DEPTH, MAX_JSON_INPUT_BYTES,
        MAX_JSON_VALUES,
    };

    fn reject(input: &str, expected: &str) {
        let error = parse_json(input).expect_err("malformed JSON was accepted");
        assert!(
            error.message().contains(expected),
            "expected {expected:?} in {error} for {input:?}",
        );
        assert!(error.offset() <= input.len());
    }

    fn main() {
        let document = parse_json(
            r#"{
                "null": null,
                "truth": true,
                "text": "raw-é and \uD83D\uDE42",
                "array": [false, 18446744073709551615, -9223372036854775808, -12.5e2],
                "object": {"escaped/key": "line\nfeed"}
            }"#,
        )
        .unwrap();
        assert_eq!(document.kind_name(), "object");
        assert_eq!(document.as_object().unwrap().len(), 5);
        assert!(document.member("null").unwrap().is_null());
        assert_eq!(document.member("truth").and_then(JsonValue::as_bool), Some(true));
        assert_eq!(
            document.member("text").and_then(JsonValue::as_str),
            Some("raw-é and 🙂"),
        );

        let values = document
            .member("array")
            .and_then(JsonValue::as_array)
            .unwrap();
        assert_eq!(values[0].as_bool(), Some(false));
        let unsigned = values[1].as_number().unwrap();
        assert_eq!(unsigned.as_u64(), Some(u64::MAX));
        assert_eq!(unsigned.as_i64(), None);
        assert!(unsigned.is_integer());
        let signed = values[2].as_number().unwrap();
        assert_eq!(signed.as_i64(), Some(i64::MIN));
        assert_eq!(signed.as_u64(), None);
        let floating = values[3].as_number().unwrap();
        assert_eq!(floating.as_f64(), -1250.0);
        assert!(!floating.is_integer());
        assert_eq!(
            document
                .member("object")
                .unwrap()
                .member("escaped/key")
                .and_then(JsonValue::as_str),
            Some("line\nfeed"),
        );
        assert!(matches!(
            parse_json("-0").unwrap(),
            JsonValue::Number(JsonNumber::Signed(0))
        ));
        assert_eq!(parse_json("[]").unwrap().as_array().unwrap(), &[]);
        assert_eq!(parse_json("{}").unwrap().as_object().unwrap(), &[]);

        reject(r#"{"a": 1, "a": 2}"#, "duplicate object key");
        reject(r#"{"a": 1, "\u0061": 2}"#, "duplicate object key");
        reject("null true", "trailing data");
        reject(r#""\x""#, "invalid JSON string escape");
        reject(r#""\u12x4""#, "invalid hexadecimal digit");
        reject(r#""\uD800""#, "high surrogate");
        reject(r#""\uD800\u0041""#, "low surrogate");
        reject(r#""\uDC00""#, "unpaired low surrogate");
        reject("\"line\nbreak\"", "control character");
        reject(r#""unterminated"#, "unterminated JSON string");
        reject("", "expected a JSON value");
        reject("tru", "invalid JSON literal");
        reject("[1,]", "expected a JSON value");
        reject(r#"{"a" 1}"#, "expected ':'");
        reject("{]", "quoted object key");
        reject("01", "leading zeros");
        reject("1.", "decimal point");
        reject("1e", "exponent");
        reject("--1", "expected a digit");
        reject("18446744073709551616", "unsigned integer");
        reject("-9223372036854775809", "signed integer");
        reject("1e400", "finite f64 range");
        reject("-1e400", "finite f64 range");

        let too_deep = format!(
            "{}0{}",
            "[".repeat(MAX_JSON_DEPTH + 2),
            "]".repeat(MAX_JSON_DEPTH + 2),
        );
        reject(&too_deep, "nesting exceeds");
        reject(&" ".repeat(MAX_JSON_INPUT_BYTES + 1), "input exceeds");

        let too_many_values = format!(
            "[{}]",
            std::iter::repeat("0")
                .take(MAX_JSON_VALUES + 1)
                .collect::<Vec<_>>()
                .join(","),
        );
        reject(&too_many_values, "document exceeds");

        println!("strict policy JSON parser passed");
    }
    '''
).lstrip()
