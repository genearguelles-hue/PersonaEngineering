package com.personaengineered.framework.selenium.extensions;

import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.TestExecutionExceptionHandler;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;

import java.io.File;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public class ScreenshotOnFailureExtension implements TestExecutionExceptionHandler {

    @Override
    public void handleTestExecutionException(
            ExtensionContext context,
            Throwable throwable
    ) throws Throwable {

        Object testInstance = context.getRequiredTestInstance();
        WebDriver driver = extractDriver(testInstance);

        if (driver != null) {
            captureFailureScreenshot(context, driver);
        } else {
            System.err.println("Unable to capture screenshot: WebDriver not found.");
        }

        throw throwable;
    }

    private void captureFailureScreenshot(ExtensionContext context, WebDriver driver) {
        try {
            File screenshot = ((TakesScreenshot) driver).getScreenshotAs(OutputType.FILE);

            String timestamp = LocalDateTime.now()
                    .format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"));

            String safeTestName = context.getDisplayName()
                    .replaceAll("[^a-zA-Z0-9-_]", "_");

            Path screenshotDir = Path.of("target", "screenshots");
            Files.createDirectories(screenshotDir);

            Path destination = screenshotDir.resolve(
                    safeTestName + "-FAILED-" + timestamp + ".png"
            );

            Files.copy(screenshot.toPath(), destination);

            System.out.println("Failure screenshot captured: " + destination.toAbsolutePath());

        } catch (IOException e) {
            System.err.println("Unable to capture failure screenshot: " + e.getMessage());
        } catch (Exception e) {
            System.err.println("Unable to capture failure screenshot: " + e.getMessage());
        }
    }

    private WebDriver extractDriver(Object testInstance) {
        Class<?> currentClass = testInstance.getClass();

        while (currentClass != null) {
            try {
                Field driverField = currentClass.getDeclaredField("driver");
                driverField.setAccessible(true);
                return (WebDriver) driverField.get(testInstance);
            } catch (NoSuchFieldException e) {
                currentClass = currentClass.getSuperclass();
            } catch (IllegalAccessException e) {
                return null;
            }
        }

        return null;
    }
}