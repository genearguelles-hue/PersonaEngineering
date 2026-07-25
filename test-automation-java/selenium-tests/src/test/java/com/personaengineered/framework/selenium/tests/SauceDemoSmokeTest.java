package com.personaengineered.framework.selenium.tests;

import com.personaengineered.framework.selenium.base.BaseUiTest;
import com.personaengineered.framework.selenium.pages.CartPage;
import com.personaengineered.framework.selenium.pages.CheckoutCompletePage;
import com.personaengineered.framework.selenium.pages.CheckoutPage;
import com.personaengineered.framework.selenium.pages.InventoryPage;
import com.personaengineered.framework.selenium.pages.LoginPage;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

public class SauceDemoSmokeTest extends BaseUiTest {

    private static final String VALID_USERNAME = "standard_user";
    private static final String LOCKED_USERNAME = "locked_out_user";
    private static final String PASSWORD = "secret_sauce";

    @Test
    @DisplayName("Smoke: valid user can login, add product to cart, checkout, and logout")
    void validUserCanCompleteCheckoutSmokeFlow() {
        LoginPage loginPage = new LoginPage(driver).open(BASE_URL);

        InventoryPage inventoryPage = loginPage.loginAsValidUser(VALID_USERNAME, PASSWORD);

        assertTrue(inventoryPage.isLoaded(), "Inventory page should be loaded");

        inventoryPage.addItemToCartByName("Sauce Labs Backpack");

        CartPage cartPage = inventoryPage.openCart();

        assertTrue(
                cartPage.containsItem("Sauce Labs Backpack"),
                "Cart should contain Sauce Labs Backpack"
        );

        CheckoutPage checkoutPage = cartPage.startCheckout()
                .enterCheckoutInformation("Gene", "Arguelles", "60601");

        assertTrue(
                checkoutPage.isSummaryDisplayed(),
                "Checkout summary should be visible"
        );

        CheckoutCompletePage completePage = checkoutPage.finishCheckout();

        assertEquals(
                "Thank you for your order!",
                completePage.getConfirmationMessage(),
                "Order confirmation should be displayed"
        );

        LoginPage returnedLoginPage = completePage.logout();

        assertTrue(
                returnedLoginPage.isLoginButtonDisplayed(),
                "Login button should be visible after logout"
        );
    }

    @Test
    @DisplayName("Smoke: locked out user cannot login")
    void lockedOutUserCannotLogin() {
        LoginPage loginPage = new LoginPage(driver).open(BASE_URL);

        loginPage.loginExpectingFailure(LOCKED_USERNAME, PASSWORD);

        assertTrue(
                loginPage.getErrorMessage().contains("locked out"),
                "Locked out user should receive a locked out error message"
        );
    }
}