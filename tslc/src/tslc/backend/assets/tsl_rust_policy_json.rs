//! Strict, standard-library-only JSON parsing for generated Rust build scripts.

#![allow(dead_code)]

use std::collections::HashSet;
use std::error::Error;
use std::fmt;

pub const MAX_JSON_INPUT_BYTES: usize = 1024 * 1024;
pub const MAX_JSON_DEPTH: usize = 64;
pub const MAX_JSON_VALUES: usize = 65_536;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum JsonNumber {
    Unsigned(u64),
    Signed(i64),
    Float(f64),
}

impl JsonNumber {
    pub fn as_u64(&self) -> Option<u64> {
        match self {
            Self::Unsigned(value) => Some(*value),
            Self::Signed(_) | Self::Float(_) => None,
        }
    }

    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Self::Unsigned(value) => i64::try_from(*value).ok(),
            Self::Signed(value) => Some(*value),
            Self::Float(_) => None,
        }
    }

    pub fn as_f64(&self) -> f64 {
        match self {
            Self::Unsigned(value) => *value as f64,
            Self::Signed(value) => *value as f64,
            Self::Float(value) => *value,
        }
    }

    pub fn is_integer(&self) -> bool {
        !matches!(self, Self::Float(_))
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum JsonValue {
    Null,
    Bool(bool),
    Number(JsonNumber),
    String(String),
    Array(Vec<JsonValue>),
    Object(Vec<(String, JsonValue)>),
}

impl JsonValue {
    pub fn is_null(&self) -> bool {
        matches!(self, Self::Null)
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            Self::Bool(value) => Some(*value),
            _ => None,
        }
    }

    pub fn as_number(&self) -> Option<&JsonNumber> {
        match self {
            Self::Number(value) => Some(value),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Self::String(value) => Some(value),
            _ => None,
        }
    }

    pub fn as_array(&self) -> Option<&[JsonValue]> {
        match self {
            Self::Array(values) => Some(values),
            _ => None,
        }
    }

    pub fn as_object(&self) -> Option<&[(String, JsonValue)]> {
        match self {
            Self::Object(members) => Some(members),
            _ => None,
        }
    }

    pub fn member(&self, name: &str) -> Option<&JsonValue> {
        self.as_object()?
            .iter()
            .find_map(|(key, value)| (key == name).then_some(value))
    }

    pub fn kind_name(&self) -> &'static str {
        match self {
            Self::Null => "null",
            Self::Bool(_) => "boolean",
            Self::Number(_) => "number",
            Self::String(_) => "string",
            Self::Array(_) => "array",
            Self::Object(_) => "object",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct JsonError {
    offset: usize,
    message: String,
}

impl JsonError {
    fn new(offset: usize, message: impl Into<String>) -> Self {
        Self {
            offset,
            message: message.into(),
        }
    }

    pub fn offset(&self) -> usize {
        self.offset
    }

    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for JsonError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "invalid JSON at byte {}: {}",
            self.offset, self.message
        )
    }
}

impl Error for JsonError {}

pub fn parse_json(input: &str) -> Result<JsonValue, JsonError> {
    if input.len() > MAX_JSON_INPUT_BYTES {
        return Err(JsonError::new(
            MAX_JSON_INPUT_BYTES,
            format!("input exceeds the {MAX_JSON_INPUT_BYTES}-byte policy limit"),
        ));
    }

    let mut parser = Parser {
        input: input.as_bytes(),
        position: 0,
        value_count: 0,
    };
    parser.skip_whitespace();
    let value = parser.parse_value(0)?;
    parser.skip_whitespace();
    if parser.peek().is_some() {
        return Err(parser.error("trailing data after the JSON value"));
    }
    Ok(value)
}

struct Parser<'a> {
    input: &'a [u8],
    position: usize,
    value_count: usize,
}

impl Parser<'_> {
    fn parse_value(&mut self, depth: usize) -> Result<JsonValue, JsonError> {
        if depth > MAX_JSON_DEPTH {
            return Err(self.error(format!(
                "nesting exceeds the {MAX_JSON_DEPTH}-level policy limit"
            )));
        }
        self.value_count += 1;
        if self.value_count > MAX_JSON_VALUES {
            return Err(self.error(format!(
                "document exceeds the {MAX_JSON_VALUES}-value policy limit"
            )));
        }

        match self.peek() {
            Some(b'n') => {
                self.consume_literal(b"null")?;
                Ok(JsonValue::Null)
            }
            Some(b't') => {
                self.consume_literal(b"true")?;
                Ok(JsonValue::Bool(true))
            }
            Some(b'f') => {
                self.consume_literal(b"false")?;
                Ok(JsonValue::Bool(false))
            }
            Some(b'"') => self.parse_string().map(JsonValue::String),
            Some(b'[') => self.parse_array(depth),
            Some(b'{') => self.parse_object(depth),
            Some(b'-' | b'0'..=b'9') => self.parse_number().map(JsonValue::Number),
            Some(value) => Err(self.error(format!(
                "unexpected byte 0x{value:02x}; expected a JSON value"
            ))),
            None => Err(self.error("expected a JSON value")),
        }
    }

    fn parse_array(&mut self, depth: usize) -> Result<JsonValue, JsonError> {
        self.position += 1;
        self.skip_whitespace();
        let mut values = Vec::new();
        if self.consume_if(b']') {
            return Ok(JsonValue::Array(values));
        }

        loop {
            values.push(self.parse_value(depth + 1)?);
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => {
                    self.position += 1;
                    self.skip_whitespace();
                }
                Some(b']') => {
                    self.position += 1;
                    return Ok(JsonValue::Array(values));
                }
                _ => return Err(self.error("expected ',' or ']' after an array value")),
            }
        }
    }

    fn parse_object(&mut self, depth: usize) -> Result<JsonValue, JsonError> {
        self.position += 1;
        self.skip_whitespace();
        let mut members = Vec::new();
        let mut keys = HashSet::new();
        if self.consume_if(b'}') {
            return Ok(JsonValue::Object(members));
        }

        loop {
            if self.peek() != Some(b'"') {
                return Err(self.error("expected a quoted object key"));
            }
            let key_offset = self.position;
            let key = self.parse_string()?;
            if !keys.insert(key.clone()) {
                return Err(JsonError::new(
                    key_offset,
                    format!("duplicate object key {key:?}"),
                ));
            }
            self.skip_whitespace();
            if !self.consume_if(b':') {
                return Err(self.error("expected ':' after an object key"));
            }
            self.skip_whitespace();
            let value = self.parse_value(depth + 1)?;
            members.push((key, value));
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => {
                    self.position += 1;
                    self.skip_whitespace();
                }
                Some(b'}') => {
                    self.position += 1;
                    return Ok(JsonValue::Object(members));
                }
                _ => return Err(self.error("expected ',' or '}' after an object member")),
            }
        }
    }

    fn parse_string(&mut self) -> Result<String, JsonError> {
        let opening_offset = self.position;
        self.position += 1;
        let mut value = String::new();
        let mut segment_start = self.position;

        loop {
            let Some(byte) = self.peek() else {
                return Err(JsonError::new(opening_offset, "unterminated JSON string"));
            };
            match byte {
                b'"' => {
                    value.push_str(self.string_segment(segment_start, self.position));
                    self.position += 1;
                    return Ok(value);
                }
                b'\\' => {
                    value.push_str(self.string_segment(segment_start, self.position));
                    self.position += 1;
                    let escape_offset = self.position.saturating_sub(1);
                    let Some(escape) = self.peek() else {
                        return Err(JsonError::new(escape_offset, "unterminated JSON escape"));
                    };
                    self.position += 1;
                    match escape {
                        b'"' => value.push('"'),
                        b'\\' => value.push('\\'),
                        b'/' => value.push('/'),
                        b'b' => value.push('\u{0008}'),
                        b'f' => value.push('\u{000c}'),
                        b'n' => value.push('\n'),
                        b'r' => value.push('\r'),
                        b't' => value.push('\t'),
                        b'u' => value.push(self.parse_unicode_escape(escape_offset)?),
                        _ => {
                            return Err(JsonError::new(
                                escape_offset,
                                "invalid JSON string escape",
                            ));
                        }
                    }
                    segment_start = self.position;
                }
                0x00..=0x1f => {
                    return Err(self.error("unescaped control character in JSON string"));
                }
                _ => self.position += 1,
            }
        }
    }

    fn parse_unicode_escape(&mut self, escape_offset: usize) -> Result<char, JsonError> {
        let first = self.parse_hex_quad()?;
        let code_point = match first {
            0xd800..=0xdbff => {
                if self.peek() != Some(b'\\') || self.input.get(self.position + 1) != Some(&b'u') {
                    return Err(JsonError::new(
                        escape_offset,
                        "high surrogate is not followed by a low-surrogate escape",
                    ));
                }
                self.position += 2;
                let low = self.parse_hex_quad()?;
                if !(0xdc00..=0xdfff).contains(&low) {
                    return Err(JsonError::new(
                        escape_offset,
                        "high surrogate is not followed by a low surrogate",
                    ));
                }
                0x1_0000 + (((first as u32 - 0xd800) << 10) | (low as u32 - 0xdc00))
            }
            0xdc00..=0xdfff => {
                return Err(JsonError::new(
                    escape_offset,
                    "unpaired low surrogate in JSON string",
                ));
            }
            value => value as u32,
        };
        char::from_u32(code_point)
            .ok_or_else(|| JsonError::new(escape_offset, "invalid Unicode scalar in JSON string"))
    }

    fn parse_hex_quad(&mut self) -> Result<u16, JsonError> {
        let start = self.position;
        let mut value = 0u16;
        for _ in 0..4 {
            let Some(byte) = self.peek() else {
                return Err(JsonError::new(start, "incomplete Unicode escape"));
            };
            let digit = match byte {
                b'0'..=b'9' => (byte - b'0') as u16,
                b'a'..=b'f' => (byte - b'a' + 10) as u16,
                b'A'..=b'F' => (byte - b'A' + 10) as u16,
                _ => return Err(self.error("invalid hexadecimal digit in Unicode escape")),
            };
            value = value * 16 + digit;
            self.position += 1;
        }
        Ok(value)
    }

    fn parse_number(&mut self) -> Result<JsonNumber, JsonError> {
        let start = self.position;
        let negative = self.consume_if(b'-');
        match self.peek() {
            Some(b'0') => {
                self.position += 1;
                if matches!(self.peek(), Some(b'0'..=b'9')) {
                    return Err(self.error("leading zeros are not allowed in JSON numbers"));
                }
            }
            Some(b'1'..=b'9') => {
                self.consume_digits();
            }
            _ => return Err(self.error("expected a digit in JSON number")),
        }

        let mut floating = false;
        if self.consume_if(b'.') {
            floating = true;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.error("expected a digit after the decimal point"));
            }
            self.consume_digits();
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            floating = true;
            self.position += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.position += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.error("expected a digit in the JSON number exponent"));
            }
            self.consume_digits();
        }

        let spelling = std::str::from_utf8(&self.input[start..self.position])
            .expect("JSON number spelling is ASCII");
        if floating {
            let value = spelling
                .parse::<f64>()
                .map_err(|_| JsonError::new(start, "invalid floating-point number"))?;
            if !value.is_finite() {
                return Err(JsonError::new(
                    start,
                    "floating-point number is outside the finite f64 range",
                ));
            }
            Ok(JsonNumber::Float(value))
        } else if negative {
            spelling
                .parse::<i64>()
                .map(JsonNumber::Signed)
                .map_err(|_| JsonError::new(start, "signed integer is outside the i64 range"))
        } else {
            spelling
                .parse::<u64>()
                .map(JsonNumber::Unsigned)
                .map_err(|_| JsonError::new(start, "unsigned integer is outside the u64 range"))
        }
    }

    fn consume_literal(&mut self, literal: &[u8]) -> Result<(), JsonError> {
        let end = self.position.saturating_add(literal.len());
        if self.input.get(self.position..end) != Some(literal) {
            return Err(self.error("invalid JSON literal"));
        }
        self.position = end;
        Ok(())
    }

    fn consume_digits(&mut self) {
        while matches!(self.peek(), Some(b'0'..=b'9')) {
            self.position += 1;
        }
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\r' | b'\n')) {
            self.position += 1;
        }
    }

    fn consume_if(&mut self, expected: u8) -> bool {
        if self.peek() == Some(expected) {
            self.position += 1;
            true
        } else {
            false
        }
    }

    fn peek(&self) -> Option<u8> {
        self.input.get(self.position).copied()
    }

    fn string_segment(&self, start: usize, end: usize) -> &str {
        std::str::from_utf8(&self.input[start..end])
            .expect("JSON string segment comes from validated UTF-8 input")
    }

    fn error(&self, message: impl Into<String>) -> JsonError {
        JsonError::new(self.position, message)
    }
}
