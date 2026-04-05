import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val relayBaseUrl = providers.gradleProperty("relayBaseUrl")
    .orElse("https://relay.example.com/")
val relayAuthToken = providers.gradleProperty("relayAuthToken")
    .orElse("")
val relayMode = providers.gradleProperty("relayMode")
    .orElse("paper_harvest_v1")
val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties = Properties()
val hasReleaseKeystore = keystorePropertiesFile.exists()
val isReleaseTaskRequested = gradle.startParameter.taskNames.any { taskName ->
    taskName.contains("Release", ignoreCase = true)
}

if (hasReleaseKeystore) {
    keystorePropertiesFile.inputStream().use(keystoreProperties::load)
}

if (isReleaseTaskRequested && !hasReleaseKeystore) {
    error(
        "Missing Android/keystore.properties. Copy Android/keystore.properties.example " +
            "to Android/keystore.properties and fill in your release signing values first.",
    )
}

android {
    namespace = "com.peter.paperharvestshare"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.peter.paperharvestshare"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        buildConfigField("String", "RELAY_BASE_URL", "\"${relayBaseUrl.get().trimEnd('/')}\"")
        buildConfigField("String", "RELAY_AUTH_TOKEN", "\"${relayAuthToken.get()}\"")
        buildConfigField("String", "RELAY_MODE", "\"${relayMode.get()}\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                val storeFileValue = keystoreProperties.getProperty("storeFile")?.trim().orEmpty()
                check(storeFileValue.isNotEmpty()) {
                    "Android/keystore.properties is missing storeFile."
                }
                storeFile = rootProject.file(storeFileValue)
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseKeystore) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
