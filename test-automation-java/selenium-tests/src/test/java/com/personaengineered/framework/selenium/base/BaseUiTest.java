package com.personaengineered.framework.selenium.base;

import io.github.bonigarcia.wdm.WebDriverManager;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInfo;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public abstract class BaseUiTest {

    protected WebDriver driver;

    protected static final String BASE_URL = "https://www.saucedemo.com/";

    @BeforeEach
void setUp() {
    WebDriverManager.chromedriver().setup();

    ChromeOptions options = new ChromeOptions();

    String headless = System.getProperty("headless", "true");
    if (Boolean.parseBoolean(headless)) {
        options.addArguments("--headless=new");
    }

    options.addArguments("--window-size=1440,900");
    options.addArguments("--disable-gpu");
    options.addArguments("--no-sandbox");
    options.addArguments("--disable-save-password-bubble");
    options.addArguments("--disable-notifications");
    options.addArguments("--disable-popup-blocking");
    options.addArguments("--incognito");

    options.setExperimentalOption("prefs", java.util.Map.of(
            "credentials_enable_service", false,
            "profile.password_manager_enabled", false,
            "profile.password_manager_leak_detection", false
    ));

    driver = new ChromeDriver(options);
    driver.manage().timeouts().pageLoadTimeout(Duration.ofSeconds(30));
}

    @AfterEach
    void tearDown(TestInfo testInfo) {
        if (driver != null) {
            captureScreenshot(testInfo);
            driver.quit();
        }
    }

    private void captureScreenshot(TestInfo testInfo) {
        try {
            if (!(driver instanceof TakesScreenshot)) {
                return;
            }

            File screenshot = ((TakesScreenshot) driver).getScreenshotAs(OutputType.FILE);

            String timestamp = LocalDateTime.now()
                    .format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"));

            String safeTestName = testInfo.getDisplayName()
                    .replaceAll("[^a-zA-Z0-9-_]", "_");

            Path screenshotDir = Path.of("target", "screenshots");
            Files.createDirectories(screenshotDir);

            Path destination = screenshotDir.resolve(safeTestName + "-" + timestamp + ".png");

            Files.copy(screenshot.toPath(), destination);

            System.out.println("Screenshot captured: " + destination.toAbsolutePath());

        } catch (IOException e) {
            System.err.println("Unable to capture screenshot: " + e.getMessage());
        }
    }
}