# Selenium Smoke Tests

This module contains the Java Selenium smoke-test baseline for the Persona-Engineered AI Test Automation Framework.

## Purpose

The smoke-test module validates a basic end-to-end web application flow using Selenium WebDriver, JUnit 5, Maven, and the Page Object Model.

The current demonstration target is SauceDemo.

Covered flows:

- Valid user login
- Add product to cart
- Open cart
- Complete checkout
- Confirm order completion
- Logout
- Locked-out user validation

## Technology Stack

- Java 21
- Maven
- JUnit 5
- Selenium WebDriver
- ChromeDriver
- WebDriverManager
- Page Object Model

## Project Structure

```text
selenium-tests/
├── pom.xml
├── README.md
└── src/test/java/com/personaengineered/framework/selenium/
    ├── base/
    │   └── BaseUiTest.java
    ├── extensions/
    │   └── ScreenshotOnFailureExtension.java
    ├── pages/
    │   ├── LoginPage.java
    │   ├── InventoryPage.java
    │   ├── CartPage.java
    │   ├── CheckoutPage.java
    │   └── CheckoutCompletePage.java
    └── tests/
        └── SauceDemoSmokeTest.java