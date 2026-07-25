package com.personaengineered.framework.selenium.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;

public class CartPage {

    private final WebDriver driver;
    private final WebDriverWait wait;

    private final By cartItem = By.className("cart_item");
    private final By checkoutButton = By.id("checkout");

    public CartPage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(10));
        wait.until(ExpectedConditions.urlContains("/cart.html"));
    }

    public boolean containsItem(String itemName) {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(cartItem))
                .getText()
                .contains(itemName);
    }

    public CheckoutPage startCheckout() {
        wait.until(ExpectedConditions.elementToBeClickable(checkoutButton)).click();
        wait.until(ExpectedConditions.urlContains("/checkout-step-one.html"));
        return new CheckoutPage(driver);
    }
}