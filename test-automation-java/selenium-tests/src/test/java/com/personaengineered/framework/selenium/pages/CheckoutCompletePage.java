package com.personaengineered.framework.selenium.pages;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;

public class CheckoutCompletePage {

    private final WebDriver driver;
    private final WebDriverWait wait;

    private final By confirmationHeader = By.className("complete-header");
    private final By menuButton = By.id("react-burger-menu-btn");
    private final By logoutLink = By.id("logout_sidebar_link");

    public CheckoutCompletePage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(10));
        wait.until(ExpectedConditions.urlContains("/checkout-complete.html"));
    }

    public String getConfirmationMessage() {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(confirmationHeader)).getText();
    }

    public LoginPage logout() {
    WebElement menu = wait.until(ExpectedConditions.presenceOfElementLocated(menuButton));

    try {
        wait.until(ExpectedConditions.elementToBeClickable(menuButton)).click();
    } catch (Exception menuClickFailure) {
        ((org.openqa.selenium.JavascriptExecutor) driver)
                .executeScript("arguments[0].click();", menu);
    }

    WebElement logout = wait.until(ExpectedConditions.presenceOfElementLocated(logoutLink));

    try {
        wait.until(ExpectedConditions.elementToBeClickable(logoutLink)).click();
    } catch (Exception logoutClickFailure) {
        ((org.openqa.selenium.JavascriptExecutor) driver)
                .executeScript("arguments[0].click();", logout);
    }

    wait.until(ExpectedConditions.urlToBe("https://www.saucedemo.com/"));

    return new LoginPage(driver);
}
}